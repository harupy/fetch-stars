import json
import os
import re

import requests
import pandas as pd
import plotly
import plotly.express as px


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

    raise Exception("TOKEN not found")


def extract_last_page_num(link_str):
    """
    `link_str` looks like:
    ('<https://api.github.com/repositories/<repo_id>/stargazers?page=2>; '
     'rel="next", '
     '<https://api.github.com/repositories/<repo_id>/stargazers?page=231>; '
     'rel="last"')
    """
    return int(re.findall(r"\?page=(\d+)>", link_str)[-1])


def fetch_stars():
    token = get_token()
    api = GitHubApi(token)
    stargazers_end_point = "/repos/{}/{}/stargazers".format("mlflow", "mlflow")

    resp = api.get(stargazers_end_point)
    last_page_num = extract_last_page_num(resp.headers["link"])  # starts from 1

    # TODO: Call APIs asynchronously
    stars = []
    for page_num in range(1, 5 + 1):
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


def main():

    # column names
    STARRED_AT = "starred_at"
    STAR_COUNT = "star_count"
    CUMULATIVE_STAR_COUNT = "star_count"

    df = (
        pd.DataFrame(fetch_stars())
        .pipe(lambda df_: df_.assign(**{STARRED_AT: pd.to_datetime(df_[STARRED_AT])}))
        .pipe(lambda df_: df_.groupby(df_[STARRED_AT].dt.floor("d")))
        .size()
        .reset_index()
        .sort_values(STARRED_AT)
        .rename(columns={0: STAR_COUNT})
        .assign(cumulative_star_count=lambda df_: df_[STAR_COUNT].cumsum())
    )

    fig = px.scatter(df, x=STARRED_AT, y=CUMULATIVE_STAR_COUNT)
    fig.update_layout(xaxis={"title": "time (UTC)"})
    save_plotly_figure(fig, "stars.html")


if __name__ == "__main__":
    main()
