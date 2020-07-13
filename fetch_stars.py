import argparse
import json
import os
import re

import requests
import pandas as pd
import plotly
from plotly.subplots import make_subplots
import plotly.graph_objects as go


class GitHubApi(requests.Session):
    def __init__(self, token=None):
        super().__init__()
        self.headers.update({"Accept": "application/vnd.github.v3.star+json"})

        if token is not None:
            self.headers.update({"Authorization": f"token {token}"})
        self.base_url = "https://api.github.com"

    def _create_url(self, end_point):
        return self.base_url + end_point

    def get(self, end_point, *args, **kwargs):
        return super().get(self._create_url(end_point), *args, **kwargs)


def read_json(path):
    with open(path, "r") as f:
        return json.load(f)


def get_token():
    TOKEN_JSON_PATH = "github_token.json"
    if os.path.exists(TOKEN_JSON_PATH):
        return read_json(TOKEN_JSON_PATH)["token"]

    TOKEN_ENV_VAR = "GITHUB_TOKEN"
    if TOKEN_ENV_VAR in os.environ:
        return os.getenv(TOKEN_ENV_VAR)

    raise Exception("`GITHUB_TOKEN` not found")


def extract_last_page_num(link_str):
    """
    `link_str` looks like:
    ('<https://api.github.com/repositories/<repo_id>/stargazers?page=2>; '
     'rel="next", '
     '<https://api.github.com/repositories/<repo_id>/stargazers?page=231>; '
     'rel="last"')
    """
    return int(re.findall(r"\?page=(\d+)>", link_str)[-1])


def fetch_stars(owner, repo):
    token = get_token()
    api = GitHubApi(token)
    stargazers_end_point = "/repos/{}/{}/stargazers".format(owner, repo)

    resp = api.get(stargazers_end_point)
    last_page_num = extract_last_page_num(resp.headers["link"])  # starts from 1

    # TODO: Call APIs asynchronously
    stars = []
    for page_num in range(1, last_page_num + 1):
        # log progress with the api usage limit
        rate_limit_resp = api.get("/rate_limit")
        print(f"{page_num} / {last_page_num}", rate_limit_resp.json()["rate"])

        stars_resp = api.get(stargazers_end_point, params={"page": page_num})
        stars.extend(map(lambda x: {"starred_at": x["starred_at"]}, stars_resp.json()))

    return stars


def save_plotly_figure(fig, path):
    if not path.endswith(".html"):
        raise ValueError("`path` must be an HTML file")

    plotly.offline.plot(fig, filename=path, include_plotlyjs="cdn", auto_open=False)


def replace_extension(path, ext):
    if not ext.startswith("."):
        raise "`ext` must start with '.'"

    base = os.path.splitext(path)[0]
    return f"{base}{ext}"


def add_suffix(path, suffix, sep="_"):
    base, ext = os.path.splitext(path)
    return f"{base}{sep}{suffix}{ext}"


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch stars")
    parser.add_argument("-o", "--owner", help="A repository owner", required=True)
    parser.add_argument("-r", "--repo", help="A repository name", required=True)
    parser.add_argument(
        "-f",
        "--fig-path",
        help="An output figure path",
        required=False,
        default="stars.html",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # column names
    STARRED_AT = "starred_at"
    STAR_COUNT = "star_count"
    CUMULATIVE_STAR_COUNT = "cumulative_star_count"
    QUARTER = "quarter"

    def assign_quarter(df):
        return df.assign(
            **{
                QUARTER: lambda df_: df_[STARRED_AT].dt.year.astype(str)
                + "-Q"
                + df[STARRED_AT].dt.quarter.astype(str)
            }
        )

    stars = fetch_stars(args.owner, args.repo)
    df = pd.DataFrame(stars)
    csv_path = replace_extension(args.fig_path, ".csv")
    df = df.assign(**{STARRED_AT: pd.to_datetime(df[STARRED_AT])})

    # daily star count
    daily = (
        df.pipe(lambda df_: df_.groupby(df_[STARRED_AT].dt.floor("d")))
        .size()
        .reset_index()
        .sort_values(STARRED_AT)
        .rename(columns={0: STAR_COUNT})
        .assign(**{CUMULATIVE_STAR_COUNT: lambda df_: df_[STAR_COUNT].cumsum()})
    )
    daily.to_csv(add_suffix(csv_path, "daily"), index=False)

    # quarterly star count
    quarterly = (
        df.pipe(assign_quarter)
        .pipe(lambda df_: df_.groupby(QUARTER))
        .size()
        .reset_index()
        .sort_values(QUARTER)
        .rename(columns={0: STAR_COUNT})
        .assign(**{CUMULATIVE_STAR_COUNT: lambda df_: df_[STAR_COUNT].cumsum()})
    )
    quarterly.to_csv(add_suffix(csv_path, "quarterly"), index=False)

    # create plots
    scatter_options = {"mode": "markers"}
    fig = make_subplots(rows=2, cols=1, subplot_titles=["Daily", "Quarterly"])
    fig.add_trace(
        go.Scatter(
            x=daily[STARRED_AT],
            y=daily[CUMULATIVE_STAR_COUNT],
            name="Daily",
            **scatter_options,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=quarterly[QUARTER],
            y=quarterly[CUMULATIVE_STAR_COUNT],
            name="Quarterly",
            **scatter_options,
        ),
        row=2,
        col=1,
    )

    fig.update_yaxes(title_text=CUMULATIVE_STAR_COUNT, row=1, col=1)
    fig.update_yaxes(title_text=CUMULATIVE_STAR_COUNT, row=2, col=1)
    fig.update_layout(
        title_text=f"Repository URL: https://github.com/{args.owner}/{args.repo}",
        showlegend=False,
    )

    save_plotly_figure(fig, args.fig_path)


if __name__ == "__main__":
    main()
