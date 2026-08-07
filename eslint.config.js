import eslint from '@eslint/js'
import eslintConfigPrettier from 'eslint-config-prettier'
import eslintPluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import typescriptEslint from 'typescript-eslint'

export default typescriptEslint.config(
  {
    ignores: [
      'dist/**',
      'coverage/**',
      'node_modules/**',
      'public/**',
      'docs/**',
      'data/**',
      '**/*.d.ts',
    ],
  },
  {
    extends: [
      eslint.configs.recommended,
      ...typescriptEslint.configs.recommended,
      ...eslintPluginVue.configs['flat/essential'],
    ],

    files: ['**/*.{ts,vue}'],

    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: globals['shared-node-browser'],

      parserOptions: {
        parser: typescriptEslint.parser,
      },
    },

    rules: {
      'vue/multi-word-component-names': 'off',
    },
  },
  eslintConfigPrettier,
)
