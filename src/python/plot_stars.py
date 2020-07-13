import argparse
import os

import pandas as pd
import plotly
from plotly.subplots import make_subplots
import plotly.graph_objects as go


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
    parser.add_argument(
        "-c", "--csv-path", help="Input csv path", required=False, default="stars.csv",
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

    df = pd.read_csv(args.csv_path)
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
    daily.to_csv(add_suffix(args.csv_path, "daily"), index=False)

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
    quarterly.to_csv(add_suffix(args.csv_path, "quarterly"), index=False)

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
    fig.update_layout(showlegend=False)

    fig_path = replace_extension(args.csv_path, ".html")
    save_plotly_figure(fig, fig_path)


if __name__ == "__main__":
    main()
