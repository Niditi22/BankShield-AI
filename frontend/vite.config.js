import {defineConfig} from 'vite';
export default defineConfig({server:{proxy:{'/api':'http://127.0.0.1:5000','/media':'http://127.0.0.1:5000'}},build:{outDir:'../static/react',emptyOutDir:true}});
