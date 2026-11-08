/**
 * Ubiquitous tooling and dev-dependency stop-list matching
 * shared/mergewise_features/extractor.py DEV_DEPENDENCY_STOP_LIST.
 * Filters out common test/linting tools from framework pills.
 */
export const DEV_TOOLING_STOP_LIST: Set<string> = new Set([
  "pytest",
  "pytest-cov",
  "pytest-mock",
  "pytest-asyncio",
  "ruff",
  "black",
  "flake8",
  "mypy",
  "pylint",
  "isort",
  "pre-commit",
  "tox",
  "coverage",
  "eslint",
  "prettier",
  "jest",
  "mocha",
  "chai",
  "babel",
  "webpack",
  "typescript",
  "ts-node",
  "nodemon",
  "vitest",
  "biome",
  "stylelint",
  "husky",
  "lint-staged",
  "build",
  "wheel",
  "setuptools",
  "twine",
  "npm",
  "yarn",
  "pnpm",
]);

export function isStoppedTool(toolName: string): boolean {
  if (!toolName) return true;
  const clean = toolName.toLowerCase().trim();
  const normalized = clean.replace(/_/g, "-");

  if (DEV_TOOLING_STOP_LIST.has(clean) || DEV_TOOLING_STOP_LIST.has(normalized)) {
    return true;
  }

  // Type stubs
  if (normalized.startsWith("types-") || normalized.startsWith("@types/")) {
    return true;
  }

  return false;
}

