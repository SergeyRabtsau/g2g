import exceptions
import time
import ConfigParser

import github
import graphitesend


def timeit(method):
  """Decorator that track execution time."""
  def timed(*args, **kw):
    ts = time.time()
    result = method(*args, **kw)
    te = time.time()
    if 'log_time' in kw:
      name = kw.get('log_name', method.__name__.upper())
      kw['log_time'][name] = int((te - ts) * 1000)
    else:
      print '%r  %2.2f ms' % \
            (method.__name__, (te - ts) * 1000)
    return result

  return timed


class GithubClient(object):
  """Class to work with Github API."""
  def __init__(self, **kwargs):
    self._attempts = kwargs.pop('attempts')
    self._repo_name = kwargs.pop('repo_name')
    self._github = github.Github(
      login_or_token=kwargs.pop("api_token"),
      **kwargs)

  @timeit
  def get_pr_data(self, pr_state):
    """Get graphite-like dictionary from repo about authors and assignees."""
    repo = self._github.get_repo(self._repo_name)
    temp_list = list(repo.get_issues(state=pr_state))

    all_issues = []
    attempts = 0
    # get pr only
    while attempts <= self._attempts:
      try:
        all_issues = [item for item in temp_list if
                      item.pull_request is not None]
        break
      except (github.GithubException, exceptions.IOError) as exc:
        attempts += 1
        print exc

    # get list of assignees names from issues
    all_assignee_names = [
      assignee.login
      for issue in all_issues
      for assignee in issue.assignees
      ]

    # get list of authors names from issues
    all_authors_name = [
      issue.user.login
      for issue in all_issues
      ]

    # get list of labels from issues
    all_labels = [
      label.name
      for issue in all_issues
      for label in issue.labels
      if not str(label.name).startswith("cla")
    ]

    res_open_by_assignees = {
      name: all_assignee_names.count(name)
      for name in sorted(set(all_assignee_names), key=lambda s: s.lower())
      }

    res_open_by_authors = {
      name: all_authors_name.count(name)
      for name in sorted(set(all_authors_name), key=lambda s: s.lower())
      }

    res_by_labels = {
      label: all_labels.count(label)
      for label in sorted(set(all_labels), key=lambda s: s.lower())
      }

    # prepare graphite dict
    graphite_stats = {}
    for name, value in res_open_by_assignees.iteritems():
      graphite_stats["{0}.assignee.{1}".format(name, pr_state)] = value

    for name, value in res_open_by_authors.iteritems():
      graphite_stats["{0}.author.{1}".format(name, pr_state)] = value

    for name, value in res_by_labels.iteritems():
      graphite_stats["pr.label.{0}.{1}".format(name, pr_state)] = value

    graphite_stats["pr.total_%s" % pr_state] = len(all_issues)
    return graphite_stats


class GraphiteClient(object):
  """Class to work with graphite."""
  def __init__(self, **kwargs):
    self._client = graphitesend.init(
      prefix='github.stats', system_name='ggrc',
      lowercase_metric_names=True, **kwargs)

  @timeit
  def send_data(self, github_stats_data):
    """Send data to graphite server."""
    result = github_stats_data
    if isinstance(github_stats_data, tuple) and len(github_stats_data) == 2:
      result = dict(github_stats_data[0], **github_stats_data[1])
    self._client.send_dict(result)


class ConfigClient(object):
  """Class to work with config file."""
  def __init__(self, file_name):
    self._cfg = ConfigParser.ConfigParser()
    self._cfg.read(file_name)

  @timeit
  def get_options_dict(self, section_name=None):
    """Read config file and return dict of options with their values."""
    sections = self._cfg.sections()
    if section_name is not None and self._cfg.has_section(section_name):
      sections = [section_name]

    return {
      option: ConfigClient.save_cast(
        self._cfg.get(section, option), int, self._cfg.get(section, option))
      for section in sections
      for option in self._cfg.options(section)
      }

  @staticmethod
  def save_cast(val, to_type, default=None):
    """Return casted value if casting is successful otherwise return default."""
    try:
      return to_type(val)
    except (ValueError, TypeError):
      return default


if __name__ == "__main__":
  cfg = ConfigClient("config.ini")
  gpc = GraphiteClient(**cfg.get_options_dict("graphite"))
  ghc = GithubClient(**cfg.get_options_dict("github"))
  gpc.send_data(ghc.get_pr_data("open"))
