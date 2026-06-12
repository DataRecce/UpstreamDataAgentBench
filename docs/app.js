const REPO_BASE_URL = "https://github.com/ucbepic/DataAgentBench/tree/main";
const RAW_BASE_URL = "https://raw.githubusercontent.com/ucbepic/DataAgentBench/main";
const DATASET_FOLDER_MAP = {
  agnews: "query_agnews",
  bookreview: "query_bookreview",
  crmarenapro: "query_crmarenapro",
  deps_dev_v1: "query_DEPS_DEV_V1",
  github_repos: "query_GITHUB_REPOS",
  googlelocal: "query_googlelocal",
  music_brainz_20k: "query_music_brainz_20k",
  pancancer_atlas: "query_PANCANCER_ATLAS",
  patents: "query_PATENTS",
  stockindex: "query_stockindex",
  stockmarket: "query_stockmarket",
  yelp: "query_yelp"
};
const DATASET_METADATA = {
  agnews: { dbCount: 2, dbms: "MongoDB, SQLite", tableCount: 3, queryCount: 4 },
  bookreview: { dbCount: 2, dbms: "PostgreSQL, SQLite", tableCount: 2, queryCount: 3 },
  crmarenapro: { dbCount: 6, dbms: "DuckDB, PostgreSQL, SQLite", tableCount: 27, queryCount: 13 },
  deps_dev_v1: { dbCount: 2, dbms: "DuckDB, SQLite", tableCount: 3, queryCount: 2 },
  github_repos: { dbCount: 2, dbms: "DuckDB, SQLite", tableCount: 6, queryCount: 4 },
  googlelocal: { dbCount: 2, dbms: "PostgreSQL, SQLite", tableCount: 2, queryCount: 4 },
  music_brainz_20k: { dbCount: 2, dbms: "DuckDB, SQLite", tableCount: 2, queryCount: 3 },
  pancancer_atlas: { dbCount: 2, dbms: "DuckDB, PostgreSQL", tableCount: 3, queryCount: 3 },
  patents: { dbCount: 2, dbms: "PostgreSQL, SQLite", tableCount: 2, queryCount: 3 },
  stockindex: { dbCount: 2, dbms: "DuckDB, SQLite", tableCount: 2, queryCount: 3 },
  stockmarket: { dbCount: 2, dbms: "DuckDB, SQLite", tableCount: 2754, queryCount: 5 },
  yelp: { dbCount: 2, dbms: "DuckDB, MongoDB", tableCount: 5, queryCount: 7 }
};
const DATASET_ALIASES = {
  deps_dev: "deps_dev_v1",
  music_brainz: "music_brainz_20k",
  pancancer: "pancancer_atlas"
};

const state = {
  leaderboards: null,
  queries: [],
  selectedDataset: "all",
  agentMatrix: null,
  dbPreviewCache: {}
};

function formatCompactNumber(value) {
  const fixed = Number(value).toFixed(4);
  return fixed.replace(/\.?0+$/, "");
}

function formatPercent(value) {
  return `${Number(value).toFixed(1)}%`;
}

function formatPercentFromScore(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (typeof text === "string") {
    element.textContent = text;
  }
  return element;
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

function getNumericValue(value) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return null;
  }
  return numberValue;
}

function getRowMax(row, columns) {
  const values = columns
    .map((column) => getNumericValue(row[column.key]))
    .filter((value) => value !== null);
  if (values.length === 0) {
    return null;
  }
  return Math.max(...values);
}

function normalizeDatasetName(dataset) {
  if (DATASET_ALIASES[dataset]) {
    return DATASET_ALIASES[dataset];
  }
  return dataset;
}

function buildAgentMatrix(leaderboards) {
  const columns = [
    { key: "promptql_opus46", label: "PromptQL Opus 4.6" },
    { key: "promptql_gemini31pro", label: "PromptQL Gemini 3.1 Pro" },
    { key: "promptql_gpt52", label: "PromptQL GPT-5.2" },
    { key: "react_gpt52", label: "GPT-5.2 ReAct" },
    { key: "react_gpt5mini", label: "GPT-5-mini ReAct" },
    { key: "react_gemini3pro", label: "Gemini-3-Pro ReAct" },
    { key: "react_gemini25flash", label: "Gemini-2.5-Flash ReAct" },
    { key: "react_kimik2", label: "Kimi-K2 ReAct" }
  ];
  const rowsByDataset = {};
  Object.keys(DATASET_METADATA).forEach((dataset) => {
    rowsByDataset[dataset] = { dataset };
  });

  leaderboards.promptqlStratified.rows.forEach((row) => {
    const datasetKey = normalizeDatasetName(row.dataset);
    if (!rowsByDataset[datasetKey]) {
      rowsByDataset[datasetKey] = { dataset: datasetKey };
    }
    rowsByDataset[datasetKey].promptql_opus46 = row.opus46;
    rowsByDataset[datasetKey].promptql_gemini31pro = row.gemini31pro;
    rowsByDataset[datasetKey].promptql_gpt52 = row.gpt52;
  });

  leaderboards.baselineStratified.rows.forEach((row) => {
    const datasetKey = normalizeDatasetName(row.dataset);
    if (!rowsByDataset[datasetKey]) {
      rowsByDataset[datasetKey] = { dataset: datasetKey };
    }
    rowsByDataset[datasetKey].react_gpt52 = row.gpt52 * 100;
    rowsByDataset[datasetKey].react_gpt5mini = row.gpt5mini * 100;
    rowsByDataset[datasetKey].react_gemini3pro = row.gemini3pro * 100;
    rowsByDataset[datasetKey].react_gemini25flash = row.gemini25flash * 100;
    rowsByDataset[datasetKey].react_kimik2 = row.kimik2 * 100;
  });

  const overall = {
    dataset: "Overall",
    promptql_opus46: leaderboards.promptqlStratified.overall.opus46,
    promptql_gemini31pro: leaderboards.promptqlStratified.overall.gemini31pro,
    promptql_gpt52: leaderboards.promptqlStratified.overall.gpt52,
    react_gpt52: leaderboards.baselineStratified.overall.gpt52 * 100,
    react_gpt5mini: leaderboards.baselineStratified.overall.gpt5mini * 100,
    react_gemini3pro: leaderboards.baselineStratified.overall.gemini3pro * 100,
    react_gemini25flash: leaderboards.baselineStratified.overall.gemini25flash * 100,
    react_kimik2: leaderboards.baselineStratified.overall.kimik2 * 100
  };
  return {
    columns,
    rows: Object.values(rowsByDataset),
    overall
  };
}

function renderOverallLeaderboard(rows) {
  const tbody = document.querySelector("#overall-table tbody");
  tbody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");

    const rankTd = createElement("td", "num", String(row.rank));
    const agentTd = createElement("td", "", row.agent);
    const teamTd = document.createElement("td");
    const teamLink = createElement("a", "", row.team);
    teamLink.href = row.teamUrl;
    teamLink.target = "_blank";
    teamLink.rel = "noopener noreferrer";
    teamTd.appendChild(teamLink);
    const trialsTd = createElement("td", "num", String(row.trials));
    const passTd = createElement("td", "num", formatPercentFromScore(row.passAt1));
    const dateTd = createElement("td", "", row.date);
    const prTd = document.createElement("td");
    if (row.prUrl) {
      const prMatch = row.prUrl.match(/\/pull\/(\d+)/);
      const prLabel = prMatch ? `PR #${prMatch[1]}` : "PR";
      const prLink = createElement("a", "", prLabel);
      prLink.href = row.prUrl;
      prLink.target = "_blank";
      prLink.rel = "noopener noreferrer";
      prTd.appendChild(prLink);
    } else {
      prTd.textContent = "—";
    }

    tr.appendChild(rankTd);
    tr.appendChild(agentTd);
    tr.appendChild(teamTd);
    tr.appendChild(trialsTd);
    tr.appendChild(passTd);
    tr.appendChild(dateTd);
    tr.appendChild(prTd);
    tbody.appendChild(tr);
  });
}

function renderMatrixTable(options) {
  const table = document.getElementById(options.tableId);
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  const tfoot = table.querySelector("tfoot");
  thead.innerHTML = "";
  tbody.innerHTML = "";
  tfoot.innerHTML = "";

  const headerTr = document.createElement("tr");
  headerTr.appendChild(createElement("th", "", "Dataset"));
  options.columns.forEach((col) => {
    headerTr.appendChild(createElement("th", "num", col.label));
  });
  thead.appendChild(headerTr);

  function makeCells(row) {
    const maxVal = getRowMax(row, options.columns);
    return options.columns.map((col) => {
      const v = getNumericValue(row[col.key]);
      const td = createElement("td", "num", v === null ? "—" : options.formatValue(v));
      if (v === null) td.classList.add("muted");
      else if (v === 0) td.classList.add("cell-zero");
      else if (maxVal !== null && v === maxVal) td.classList.add("cell-best");
      return td;
    });
  }

  options.rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.appendChild(createElement("td", "", row.dataset));
    makeCells(row).forEach((td) => tr.appendChild(td));
    tbody.appendChild(tr);
  });

  const footerTr = document.createElement("tr");
  footerTr.appendChild(createElement("td", "", options.overall.dataset));
  makeCells(options.overall).forEach((td) => footerTr.appendChild(td));
  tfoot.appendChild(footerTr);
}

function populateAgentSelector(columns) {
  const selector = document.getElementById("agent-selector");
  selector.innerHTML = "";
  const datasetOption = document.createElement("option");
  datasetOption.value = "dataset";
  datasetOption.textContent = "Dataset (A–Z)";
  selector.appendChild(datasetOption);
  columns.forEach((column) => {
    const option = document.createElement("option");
    option.value = column.key;
    option.textContent = column.label;
    selector.appendChild(option);
  });
}

function getSortedRowsByAgent(rows, selectedAgent, order) {
  const isAscending = order === "asc";
  return [...rows].sort((firstRow, secondRow) => {
    if (selectedAgent === "dataset") {
      const datasetCompare = firstRow.dataset.localeCompare(secondRow.dataset);
      return isAscending ? datasetCompare : -datasetCompare;
    }
    const valueA = getNumericValue(firstRow[selectedAgent]);
    const valueB = getNumericValue(secondRow[selectedAgent]);
    if (valueA === null && valueB === null) {
      return firstRow.dataset.localeCompare(secondRow.dataset);
    }
    if (valueA === null) {
      return 1;
    }
    if (valueB === null) {
      return -1;
    }
    if (valueA !== valueB) {
      return isAscending ? valueA - valueB : valueB - valueA;
    }
    return firstRow.dataset.localeCompare(secondRow.dataset);
  });
}

function renderAgentTable() {
  const selectedAgent = document.getElementById("agent-selector").value;
  const sortOrder = document.getElementById("agent-order").value;
  const sortedRows = getSortedRowsByAgent(state.agentMatrix.rows, selectedAgent, sortOrder);
  renderMatrixTable({
    tableId: "agent-table",
    columns: state.agentMatrix.columns,
    rows: sortedRows,
    overall: state.agentMatrix.overall,
    formatValue: formatPercent
  });
}

function setupAgentControls() {
  populateAgentSelector(state.agentMatrix.columns);
  document.getElementById("agent-selector").value = "promptql_gemini31pro";
  document.getElementById("agent-order").value = "desc";
  document.getElementById("agent-selector").addEventListener("change", renderAgentTable);
  document.getElementById("agent-order").addEventListener("change", renderAgentTable);
}

function getQueryFolderUrl(dataset, queryId) {
  const datasetFolder = DATASET_FOLDER_MAP[dataset];
  if (!datasetFolder) {
    return null;
  }
  const normalizedQueryId = queryId.startsWith("query") ? queryId : `query${queryId}`;
  return `${REPO_BASE_URL}/${datasetFolder}/${normalizedQueryId}`;
}

function getDbDescriptionUrl(dataset, withHint = false) {
  const datasetFolder = DATASET_FOLDER_MAP[dataset];
  if (!datasetFolder) {
    return null;
  }
  const fileName = withHint ? "db_description_withhint.txt" : "db_description.txt";
  return `${REPO_BASE_URL}/${datasetFolder}/${fileName}`;
}

function getRawDbDescriptionUrl(dataset) {
  const datasetFolder = DATASET_FOLDER_MAP[dataset];
  if (!datasetFolder) {
    return null;
  }
  return `${RAW_BASE_URL}/${datasetFolder}/db_description.txt`;
}

function getQueryNumericId(query) {
  const match = query.queryId.match(/\d+/);
  if (!match) {
    return Number.MAX_SAFE_INTEGER;
  }
  return Number(match[0]);
}

function getQueryPreview(text) {
  const firstSentence = text.replace(/\s+/g, " ").trim().split(/[?\n]/)[0];
  if (firstSentence.length <= 90) {
    return firstSentence + "?";
  }
  return firstSentence.slice(0, 87) + "...";
}

function getFilteredQueries() {
  const searchTerm = document.getElementById("query-search").value.trim().toLowerCase();
  return state.queries
    .filter((query) => (state.selectedDataset === "all" ? true : query.dataset === state.selectedDataset))
    .filter((query) => {
      if (searchTerm.length === 0) {
        return true;
      }
      const searchableText = `${query.dataset} ${query.queryId} ${query.text}`.toLowerCase();
      return searchableText.includes(searchTerm);
    })
    .sort((firstQuery, secondQuery) => {
      if (firstQuery.dataset !== secondQuery.dataset) {
        return firstQuery.dataset.localeCompare(secondQuery.dataset);
      }
      return getQueryNumericId(firstQuery) - getQueryNumericId(secondQuery);
    });
}

function renderDatasetSidebar() {
  const listEl = document.getElementById("dataset-list");
  listEl.innerHTML = "";

  function makeBtn(label, count, key, extraClass) {
    const btn = createElement("button", `ds-btn${extraClass ? " " + extraClass : ""}`, "");
    btn.type = "button";
    btn.appendChild(createElement("span", "", label));
    btn.appendChild(createElement("span", "ds-count", String(count)));
    if (state.selectedDataset === key) btn.classList.add("active");
    btn.addEventListener("click", () => {
      state.selectedDataset = key;
      renderQueryExplorer();
    });
    return btn;
  }

  listEl.appendChild(makeBtn("All datasets", state.queries.length, "all", "ds-btn-all"));
  Object.keys(DATASET_METADATA).forEach((dataset) => {
    const qCount = state.queries.filter((q) => q.dataset === dataset).length;
    listEl.appendChild(makeBtn(dataset, qCount, dataset, ""));
  });
}

async function loadDbPreview(dataset) {
  if (state.dbPreviewCache[dataset]) {
    return state.dbPreviewCache[dataset];
  }
  const rawUrl = getRawDbDescriptionUrl(dataset);
  if (!rawUrl) {
    state.dbPreviewCache[dataset] = "No db_description.txt mapping found.";
    return state.dbPreviewCache[dataset];
  }
  try {
    const response = await fetch(rawUrl);
    if (!response.ok) {
      state.dbPreviewCache[dataset] = `Unable to fetch db_description.txt (${response.status}).`;
      return state.dbPreviewCache[dataset];
    }
    const text = await response.text();
    state.dbPreviewCache[dataset] = text.trim().length === 0 ? "db_description.txt is empty." : text;
    return state.dbPreviewCache[dataset];
  } catch (error) {
    state.dbPreviewCache[dataset] = `Unable to fetch db_description.txt (${error.message}).`;
    return state.dbPreviewCache[dataset];
  }
}

function renderDatasetMeta() {
  const el = document.getElementById("dataset-meta");
  el.innerHTML = "";
  if (state.selectedDataset === "all") {
    el.innerHTML = "<p class='muted' style='font-size:.85rem'>Select a dataset to see schema info.</p>";
    return;
  }
  const ds = state.selectedDataset;
  const meta = DATASET_METADATA[ds];
  const folder = DATASET_FOLDER_MAP[ds];

  const wrap = createElement("div", "ds-meta", "");
  wrap.appendChild(createElement("h3", "", ds));

  const grid = createElement("div", "ds-meta-grid", "");
  [["Databases", meta.dbCount], ["DBMSes", meta.dbms], ["Tables", meta.tableCount], ["Queries", meta.queryCount]].forEach(([label, val]) => {
    const cell = createElement("div", "ds-meta-cell", "");
    cell.appendChild(createElement("p", "ds-meta-label", label));
    cell.appendChild(createElement("p", "ds-meta-val", String(val)));
    grid.appendChild(cell);
  });
  wrap.appendChild(grid);

  const links = createElement("div", "ds-links", "");
  [[`${REPO_BASE_URL}/${folder}`, "Dataset folder"],
   [getDbDescriptionUrl(ds, false), "db_description.txt"],
   [getDbDescriptionUrl(ds, true), "db_description_withhint.txt"]
  ].forEach(([href, label]) => {
    const a = createElement("a", "ds-link", label);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    links.appendChild(a);
  });
  wrap.appendChild(links);

  const previewBtn = createElement("button", "db-preview-btn", "Preview schema");
  previewBtn.type = "button";
  const previewArea = createElement("pre", "db-preview", "");
  previewArea.style.display = "none";
  previewBtn.addEventListener("click", async () => {
    previewBtn.disabled = true;
    previewBtn.textContent = "Loading…";
    const text = await loadDbPreview(ds);
    previewArea.textContent = text;
    previewArea.style.display = "block";
    previewBtn.textContent = "Refresh";
    previewBtn.disabled = false;
  });
  wrap.appendChild(previewBtn);
  wrap.appendChild(previewArea);
  el.appendChild(wrap);
}

function createQueryItem(query) {
  const item = createElement("div", "q-item", "");
  const header = createElement("div", "q-header", "");
  header.appendChild(createElement("span", "q-pill", query.queryId));
  const text = createElement("span", "q-text-inline", query.text);
  header.appendChild(text);
  item.appendChild(header);
  const url = getQueryFolderUrl(query.dataset, query.queryId);
  if (url) {
    const link = createElement("a", "q-link", "GitHub →");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    item.appendChild(link);
  }
  return item;
}

function renderQueryList() {
  const listEl = document.getElementById("query-list");
  const countEl = document.getElementById("query-count");
  const queries = getFilteredQueries();
  countEl.textContent = `${queries.length} quer${queries.length === 1 ? "y" : "ies"}`;
  listEl.innerHTML = "";

  if (state.selectedDataset === "all") {
    const groups = {};
    queries.forEach((q) => { (groups[q.dataset] = groups[q.dataset] || []).push(q); });
    Object.keys(groups).forEach((ds) => {
      listEl.appendChild(createElement("p", "ds-group-label", ds));
      groups[ds].forEach((q) => listEl.appendChild(createQueryItem(q)));
    });
    return;
  }

  queries.forEach((q) => listEl.appendChild(createQueryItem(q)));
}

function renderQueryExplorer() {
  renderDatasetSidebar();
  renderDatasetMeta();
  renderQueryList();
}

function setUpdatedAtText(updatedAt) {
  const footerText = document.getElementById("updated-at");
  footerText.textContent = `Last updated: ${updatedAt}`;
}

async function init() {
  try {
    const [leaderboards, queries] = await Promise.all([
      loadJson("./data/leaderboards.json"),
      loadJson("./data/queries.json")
    ]);
    state.leaderboards = leaderboards;
    state.queries = queries;
    state.agentMatrix = buildAgentMatrix(leaderboards);
    renderOverallLeaderboard(leaderboards.overallLeaderboard);
    setupAgentControls();
    renderAgentTable();
    setUpdatedAtText(leaderboards.updatedAt);
    renderQueryExplorer();
  } catch (error) {
    const main = document.querySelector("main");
    main.innerHTML = `<section class="card"><h2>Failed to load data</h2><p>${error.message}</p></section>`;
  }
}

document.getElementById("query-search").addEventListener("input", renderQueryList);

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach((p) => { p.style.display = "none"; });
    document.getElementById(`tab-${btn.dataset.tab}`).style.display = "block";
  });
});

init();
