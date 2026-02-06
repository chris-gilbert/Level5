import { defineConfig } from 'vite';

export default defineConfig({
    root: '.',
    build: {
        outDir: 'dist',
        assetsDir: 'assets',
        minify: 'esbuild',
        sourcemap: false
    },
    server: {
        port: 3000,
        open: true
    }
});
