export default {
  extends: ['@commitlint/config-conventional'],
  // Dependabot group-update headers (e.g. "bump the npm_and_yarn group across 1
  // directory with 3 updates") exceed header-max-length and can't be reworded.
  ignores: [(message) => /^(chore|build|ci)\(deps(-dev)?\): bump /.test(message)],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'docs',
        'style',
        'refactor',
        'perf',
        'test',
        'build',
        'ci',
        'chore',
        'revert',
      ],
    ],
    'subject-case': [0],
    'header-max-length': [2, 'always', 72],
  },
};
