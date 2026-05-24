/**
 * Shared Pyodide + inccsv initialisation.
 *
 * Usage:
 *   import { initPyodide } from './pyodide-init.js';
 *   initPyodide((msg, isError) => { ... })
 *     .then(py => { /* use py.runPython(...) *\/ })
 *     .catch(() => {});
 *
 * Requires the Pyodide CDN script to be loaded before this module runs:
 *   <script src="https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js"></script>
 */
export async function initPyodide(onStatus) {
    try {
        onStatus('Loading Python runtime…', false);
        const pyodide = await loadPyodide();
        onStatus('Installing inccsv…', false);
        await pyodide.loadPackage('micropip');
        await pyodide.runPythonAsync(`
import micropip
await micropip.install('inccsv')
`);
        return pyodide;
    } catch (err) {
        onStatus('Failed to initialise: ' + err.message, true);
        throw err;
    }
}
