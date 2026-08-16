/**
 * dev — run the Vite dev server and `tauri dev` concurrently
 * (tauri.conf.json has no beforeDevCommand; the webview points at :5173).
 */

import { spawn } from 'node:child_process';

const vite = spawn('npx', ['vite'], { stdio: 'inherit', shell: true });
const tauri = spawn('npx', ['tauri', 'dev'], { stdio: 'inherit', shell: true });

const stop = () => {
	tauri.kill('SIGTERM');
	vite.kill('SIGTERM');
	process.exit(0);
};

process.on('SIGINT', stop);
process.on('SIGTERM', stop);

vite.on('exit', (code) => {
	if (code !== 0) {
		tauri.kill('SIGTERM');
		process.exit(code ?? 1);
	}
});
tauri.on('exit', (code) => {
	vite.kill('SIGTERM');
	process.exit(code ?? 0);
});