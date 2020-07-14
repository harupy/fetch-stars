import axios, { AxiosInstance } from "axios";
import { createObjectCsvWriter } from "csv-writer";
import * as yargs from "yargs";

type Star = {
  starred_at: string;
};

function createApi(token: string): AxiosInstance {
  return axios.create({
    baseURL: "https://api.github.com/",
    headers: {
      Accept: "application/vnd.github.v3.star+json",
      Authorization: token ? `token ${token}` : undefined,
    },
  });
}

function extractLastPage(link: string): number {
  const pattern = /\?page=(\d+)>; rel="last"/g;

  const match = pattern.exec(link);

  if (match === null) {
    return 0;
  }
  return parseInt(match[1]);
}

function getToken(): string | undefined {
  return process.env.GITHUB_TOKEN;
}

function parseArgs(): {
  [x: string]: unknown;
  owner: unknown;
  repo: unknown;
  csv_path: string;
  _: string[];
  $0: string;
} {
  const { argv } = yargs
    .option("owner", {
      alias: "o",
      description: "repository owner",
      demandOption: true,
    })
    .option("repo", {
      alias: "r",
      description: "repository name",
      demandOption: true,
    })
    .option("csv_path", {
      alias: "c",
      description: "output csv path",
      default: "stars.csv",
    })
    .help();

  return argv;
}

async function main(): Promise<void> {
  const { owner, repo, csv_path } = parseArgs();

  const token = getToken();
  if (token === undefined || token === "") {
    console.log("You need to set 'GITHUB_TOKEN'");
    return;
  }

  const api = createApi(token);
  const starEndPoint = `repos/${owner}/${repo}/stargazers`;
  const resp = await api.get(starEndPoint);
  const lastPage = extractLastPage(resp.headers.link);
  const pages = Array.from(Array(lastPage), (_, i) => i + 1);
  const urls = pages.map(page => `${starEndPoint}?page=${page}`);

  let stars: Star[] = [];
  const chunkSize = 30;
  const indices = Array.from(Array(Math.ceil(lastPage / chunkSize)).keys());

  for (const index of indices) {
    const start = index * chunkSize;
    const end = (index + 1) * chunkSize;
    const promises = urls.slice(start, end).map(url => api.get(url));

    try {
      const chunk = await Promise.all(promises);
      console.log(chunk);
      stars.concat(
        chunk
          .map(s => s.data)
          .reduce((a, b) => [...a, ...b], [])
          .map(({ starred_at }: Star) => ({ starred_at }))
      );
    } catch (err) {
      throw err;
    }
  }

  console.log(stars.length);
  console.log(stars);

  const csvWriter = createObjectCsvWriter({
    path: csv_path,
    header: [{ id: "starred_at", title: "starred_at" }],
  });

  csvWriter.writeRecords(stars).then(() => {
    console.log("Done");
  });

  const rateLimit = await api.get("rate_limit");
  console.log(rateLimit.data);
}

main();
