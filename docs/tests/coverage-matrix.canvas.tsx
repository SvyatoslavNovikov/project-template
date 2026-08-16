import {
  Button,
  Callout,
  Code,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  computeDAGLayout,
  useCanvasAction,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

/**
 * Snapshot of docs/requirements + docs/tests.
 * Canvas cannot read the repo at runtime — update this block when artifacts change.
 */
type Priority = "must" | "should" | "could";
type ReqStatus = "draft" | "review" | "approved" | "implemented" | "obsolete";
type TestStatus = "draft" | "review" | "approved" | "automated" | "obsolete";

type Requirement = {
  id: string;
  type: "system-requirement" | "nfr";
  title: string;
  status: ReqStatus;
  priority: Priority;
  epicId: string;
  epicTitle: string;
  storyId: string;
  storyTitle: string;
  storyPriority: Priority;
};

type TestCase = {
  id: string;
  title: string;
  status: TestStatus;
  verifies: string[];
};

const REQUIREMENTS: Requirement[] = [];
const TESTS: TestCase[] = [];

const COVERING: TestStatus[] = ["approved", "automated"];

type Filter = "all" | "gaps" | "covered" | "must";

function covers(test: TestCase, reqId: string): boolean {
  return test.verifies.includes(reqId);
}

function isCoveringTest(test: TestCase): boolean {
  return COVERING.includes(test.status);
}

function requirementCovered(req: Requirement): boolean {
  return TESTS.some((test) => isCoveringTest(test) && covers(test, req.id));
}

function cellKind(
  test: TestCase,
  reqId: string,
): "cover" | "draft" | "obsolete" | "none" {
  if (!covers(test, reqId)) return "none";
  if (test.status === "obsolete") return "obsolete";
  if (isCoveringTest(test)) return "cover";
  return "draft";
}

function storyCovered(storyId: string): boolean {
  const kids = REQUIREMENTS.filter(
    (req) => req.storyId === storyId && req.priority === "must",
  );
  return kids.length > 0 && kids.every(requirementCovered);
}

function epicCovered(epicId: string): boolean {
  const storyIds = [
    ...new Set(
      REQUIREMENTS.filter(
        (req) => req.epicId === epicId && req.storyPriority === "must",
      ).map((req) => req.storyId),
    ),
  ];
  return storyIds.length > 0 && storyIds.every(storyCovered);
}

function TraceGraph() {
  const theme = useHostTheme();
  const layout = computeDAGLayout({
    nodes: [
      { id: "epic" },
      { id: "us" },
      { id: "sr" },
      { id: "tc" },
    ],
    edges: [
      { from: "epic", to: "us" },
      { from: "us", to: "sr" },
      { from: "tc", to: "sr" },
    ],
    direction: "horizontal",
    nodeWidth: 132,
    nodeHeight: 36,
    rankGap: 56,
    nodeGap: 28,
    padding: 8,
  });
  const labels: Record<string, string> = {
    epic: "Epic",
    us: "User story",
    sr: "SR / NFR",
    tc: "Test case",
  };
  const edgeLabels: Record<string, string> = {
    "epic->us": "parent",
    "us->sr": "parent",
    "tc->sr": "verifies",
  };

  return (
    <svg
      width="100%"
      height={layout.height}
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      role="img"
      aria-label="Связь эпик → стори → требование и тест → требование"
    >
      {layout.edges.map((edge) => {
        const key = `${edge.from}->${edge.to}`;
        const midX = (edge.sourceX + edge.targetX) / 2;
        const midY = (edge.sourceY + edge.targetY) / 2 - 8;
        const verifies = edge.from === "tc";
        return (
          <g key={key}>
            <line
              x1={edge.sourceX}
              y1={edge.sourceY}
              x2={edge.targetX}
              y2={edge.targetY}
              stroke={verifies ? theme.accent.primary : theme.stroke.secondary}
              strokeWidth={verifies ? 2 : 1}
              strokeDasharray={verifies ? undefined : "4 3"}
            />
            <text
              x={midX}
              y={midY}
              textAnchor="middle"
              fill={theme.text.tertiary}
              fontSize={10}
            >
              {edgeLabels[key]}
            </text>
          </g>
        );
      })}
      {layout.nodes.map((node) => (
        <g key={node.id}>
          <rect
            x={node.x}
            y={node.y}
            width={132}
            height={36}
            rx={4}
            fill={node.id === "tc" ? theme.fill.secondary : theme.fill.tertiary}
            stroke={theme.stroke.tertiary}
          />
          <text
            x={node.x + 66}
            y={node.y + 23}
            textAnchor="middle"
            fill={theme.text.primary}
            fontSize={12}
          >
            {labels[node.id]}
          </text>
        </g>
      ))}
    </svg>
  );
}

function CoverageCell({ kind }: { kind: ReturnType<typeof cellKind> }) {
  const theme = useHostTheme();
  if (kind === "none") {
    return (
      <Text size="small" tone="quaternary" as="span">
        —
      </Text>
    );
  }
  const bg =
    kind === "cover"
      ? theme.fill.secondary
      : kind === "draft"
        ? theme.fill.tertiary
        : theme.bg.chrome;
  const label =
    kind === "cover" ? "covers" : kind === "draft" ? "draft" : "obsolete";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "1px 6px",
        background: bg,
        color: theme.text.primary,
        fontSize: 11,
      }}
    >
      {label}
    </span>
  );
}

function Matrix() {
  const [filter, setFilter] = useCanvasState<Filter>("coverage-filter", "all");
  const activeTests = TESTS.filter((test) => test.status !== "obsolete");
  const rows = REQUIREMENTS.filter((req) => {
    if (req.status === "obsolete") return false;
    const ok = requirementCovered(req);
    if (filter === "gaps") return !ok;
    if (filter === "covered") return ok;
    if (filter === "must") return req.priority === "must";
    return true;
  });
  if (rows.length === 0) return null;

  const headers = [
    "Requirement",
    "Epic / story",
    "Priority",
    "Covered",
    ...activeTests.map((test) => test.id),
  ];
  const tableRows = rows.map((req) => {
    const ok = requirementCovered(req);
    return [
      <span>
        <Stack gap={2}>
          <Text weight="semibold" as="span">
            {req.id}
          </Text>
          <Text size="small" tone="secondary" as="span">
            {req.type === "nfr" ? "NFR" : "SR"} · {req.title}
          </Text>
        </Stack>
      </span>,
      <Text size="small" as="span">
        {req.epicId} / {req.storyId}
      </Text>,
      req.priority,
      ok ? "yes" : "gap",
      ...activeTests.map((test) => (
        <CoverageCell kind={cellKind(test, req.id)} />
      )),
    ];
  });
  const rowTone = rows.map((req) =>
    requirementCovered(req) ? ("success" as const) : ("danger" as const),
  );

  return (
    <Stack gap={10}>
      <Row gap={8} align="center" wrap>
        <Pill active={filter === "all"} onClick={() => setFilter("all")}>
          All
        </Pill>
        <Pill active={filter === "gaps"} onClick={() => setFilter("gaps")}>
          Gaps
        </Pill>
        <Pill
          active={filter === "covered"}
          onClick={() => setFilter("covered")}
        >
          Covered
        </Pill>
        <Pill active={filter === "must"} onClick={() => setFilter("must")}>
          Must only
        </Pill>
      </Row>
      <Table
        headers={headers}
        rows={tableRows}
        rowTone={rowTone}
        striped
        stickyHeader
        columnAlign={[
          "left",
          "left",
          "left",
          "left",
          ...activeTests.map(() => "center" as const),
        ]}
      />
      <Text size="small" tone="tertiary">
        Source: snapshot of docs/requirements and docs/tests · cell counts
        toward coverage only when the test is approved or automated
      </Text>
    </Stack>
  );
}

function Summary() {
  const reqs = REQUIREMENTS.filter((req) => req.status !== "obsolete");
  if (reqs.length === 0) return null;
  const covered = reqs.filter(requirementCovered).length;
  const must = reqs.filter((req) => req.priority === "must");
  const mustCovered = must.filter(requirementCovered).length;
  const stories = [...new Set(reqs.map((req) => req.storyId))];
  const epics = [...new Set(reqs.map((req) => req.epicId))];
  const storiesOk = stories.filter(storyCovered).length;
  const epicsOk = epics.filter(epicCovered).length;
  const coveringTests = TESTS.filter(isCoveringTest).length;
  const gapTone =
    covered === reqs.length ? "success" : covered === 0 ? "danger" : "warning";

  return (
    <Grid columns={4} gap={16}>
      <Stat
        value={`${covered}/${reqs.length}`}
        label="SR/NFR covered"
        tone={gapTone}
      />
      <Stat
        value={`${mustCovered}/${must.length}`}
        label="Must requirements"
        tone={mustCovered === must.length ? "success" : "warning"}
      />
      <Stat
        value={`${storiesOk}/${stories.length}`}
        label="Stories (must kids)"
      />
      <Stat
        value={`${coveringTests}`}
        label={`Covering tests · epics ${epicsOk}/${epics.length}`}
      />
    </Grid>
  );
}

export default function CoverageMatrix() {
  const dispatch = useCanvasAction();
  const hasMatrix = REQUIREMENTS.some((req) => req.status !== "obsolete");

  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>Coverage matrix</H1>
        <Text tone="secondary">
          Unit of coverage is SR / NFR. A requirement is covered when at least
          one test with <Code>verifies</Code> is <Code>approved</Code> or{" "}
          <Code>automated</Code>. Stories and epics roll up from{" "}
          <Code>must</Code> children.
        </Text>
        <Row gap={8} wrap>
          <Button
            variant="secondary"
            onClick={() =>
              dispatch({
                type: "openFile",
                path: "docs/requirements/TRACEABILITY.md",
              })
            }
          >
            Open traceability rules
          </Button>
          <Button
            variant="ghost"
            onClick={() =>
              dispatch({
                type: "newComposerChat",
                userPrompt:
                  "Пересканируй docs/requirements и docs/tests и обнови снимок REQUIREMENTS/TESTS в canvas матрицы покрытия.",
              })
            }
          >
            Refresh snapshot from docs
          </Button>
        </Row>
      </Stack>

      <Summary />

      <Stack gap={8}>
        <H2>How verifies connects to the tree</H2>
        <TraceGraph />
        <Text size="small" tone="tertiary">
          Tests sit outside the epic → story → SR tree. Coverage is many-to-many
          via verifies, not parent/children.
        </Text>
      </Stack>

      {hasMatrix ? (
        <Stack gap={8}>
          <H2>Requirement × test</H2>
          <Matrix />
        </Stack>
      ) : null}

      <Divider />

      <H2>What a cell means</H2>
      <Table
        headers={["Cell", "Test status", "Counts as coverage"]}
        rows={[
          ["covers", "approved or automated", "yes"],
          ["draft", "draft or review", "no — test exists, not yet coverage"],
          ["obsolete", "obsolete", "no"],
          ["—", "no verifies link", "gap if no other covering test"],
        ]}
        columnAlign={["left", "left", "left"]}
        striped
      />
      <Text size="small" tone="tertiary">
        Source: docs/requirements/TRACEABILITY.md · layer 3
      </Text>

      <H3>Roll-up</H3>
      <Table
        headers={["Level", "Covered when"]}
        rows={[
          ["SR / NFR", "≥1 covering test with verifies → this ID"],
          ["User story", "every must child SR/NFR is covered"],
          ["Epic", "every must child story is covered"],
        ]}
        striped
      />

      <Callout tone="info" title="Draft notes are not coverage">
        The «Проверка» section on an SR/NFR is a test idea. Coverage starts only
        after a <Code>PRJ-T-*-tc-*</Code> file in docs/tests/cases exists with{" "}
        <Code>verifies</Code> on that requirement.
      </Callout>
    </Stack>
  );
}
