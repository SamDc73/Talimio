import typescript from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'
import importPlugin from 'eslint-plugin-import'
import promisePlugin from 'eslint-plugin-promise'
import reactPlugin from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import sonarjs from 'eslint-plugin-sonarjs'
import globals from 'globals'

// Base configuration for all JavaScript files
const baseConfig = {
  plugins: {
    import: importPlugin,
    promise: promisePlugin,
    react: reactPlugin,
    'react-hooks': reactHooks,
    'react-refresh': reactRefresh,
    sonarjs: sonarjs,
  },
  languageOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    parserOptions: {
      ecmaFeatures: { jsx: true },
    },
    globals: {
      ...globals.browser,
      ...globals.es2021,
      ...globals.node,
    },
  },
  settings: {
    react: { version: 'detect' },
    'import/resolver': {
      node: true,
    },
  },
  rules: {
    // React rules
    'react/react-in-jsx-scope': 'off',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    
    // Import rules
    'import/order': ['error', {
      'groups': ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
      'newlines-between': 'always',
      'alphabetize': { order: 'asc' }
    }],
    
    // SonarJS rules
    'sonarjs/cognitive-complexity': ['error', 15],
    'sonarjs/no-duplicate-string': 'error',
    'sonarjs/no-identical-functions': 'error',
    
    // General rules
    'no-unused-vars': ['warn', { 
      vars: 'all',
      args: 'after-used',
      ignoreRestSiblings: true,
    }],
    'no-console': 'warn',
  },
}

export default [
  // Ignore build files
  { ignores: ['dist/**', 'node_modules/**'] },
  
  // JavaScript files
  {
    files: ['**/*.{js,jsx}'],
    ...baseConfig,
    languageOptions: {
      ...baseConfig.languageOptions,
      parser: tsParser,
      parserOptions: {
        ...baseConfig.languageOptions.parserOptions,
        sourceType: 'module',
      },
    },
  },
  
  // TypeScript files
  {
    files: ['**/*.{ts,tsx}'],
    ...baseConfig,
    languageOptions: {
      ...baseConfig.languageOptions,
      parser: tsParser,
      parserOptions: {
        ...baseConfig.languageOptions.parserOptions,
      },
    },
    plugins: {
      ...baseConfig.plugins,
      '@typescript-eslint': typescript,
    },
    settings: {
      ...baseConfig.settings,
      'import/resolver': {
        ...baseConfig.settings['import/resolver'],
        typescript: true,
      },
    },
    rules: {
      ...baseConfig.rules,
      '@typescript-eslint/explicit-function-return-type': 'error',
      '@typescript-eslint/no-unused-vars': ['error', {
        vars: 'all',
        args: 'after-used',
        ignoreRestSiblings: true,
      }],
    },
  },
]
