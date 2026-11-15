import {build, context} from "esbuild";
import {readFile, readdir, writeFile} from "node:fs/promises";

const watch = process.argv.includes("--watch");
const sharedOptions = {bundle: true, format: "esm", target: "es2020"};

async function writeLicenses(metafile) {
  const packages = new Set(Object.keys(metafile.inputs).map(path => {
    const parts = path.split("/");
    const index = parts.lastIndexOf("node_modules");
    if (index < 0) return null;
    return parts[index + 1]?.startsWith("@")
      ? parts.slice(index + 1, index + 3).join("/") : parts[index + 1];
  }).filter(Boolean));
  const licenses = [];
  for (const name of [...packages].sort()) {
    const root = `node_modules/${name}`;
    const manifest = JSON.parse(await readFile(`${root}/package.json`, "utf8"));
    const paths = (await readdir(root)).filter(path => /^license/i.test(path)).sort();
    if (!paths.length) throw new Error(`Missing bundled dependency license: ${name}`);
    licenses.push(`${name} ${manifest.version}\n${await readFile(`${root}/${paths[0]}`, "utf8")}`);
  }
  await writeFile("library/static/library/generated/editor-licenses.txt", licenses.join("\n\n"));
}

function buildOptions(name, entry, outfile, licenses = false) {
  return {
    ...sharedOptions,
    entryPoints: [entry],
    outfile,
    metafile: licenses,
    plugins: [{
      name: `${name}-completion`,
      setup(pluginBuild) {
        pluginBuild.onEnd(async result => {
          if (result.errors.length) {
            if (watch) console.error(`[watch] ${name} build failed`);
            return;
          }
          if (licenses) await writeLicenses(result.metafile);
          if (watch) console.log(`[watch] ${name} build complete`);
        });
      },
    }],
  };
}

const builds = [
  buildOptions("editor", "frontend/pilot.js", "library/static/library/generated/editor-pilot.js", true),
  buildOptions("public workspace", "frontend/public-workspace.js", "library/static/library/generated/public-workspace.js"),
];

if (!watch) {
  for (const options of builds) await build(options);
} else {
  const pendingContexts = [];
  let stopping;
  function stop() {
    if (!stopping) {
      stopping = (async () => {
        const created = await Promise.allSettled(pendingContexts);
        const disposed = await Promise.allSettled(created
          .filter(result => result.status === "fulfilled")
          .map(result => result.value.dispose()));
        for (const result of disposed) {
          if (result.status === "rejected") {
            console.error("[watch] Failed to stop build context:", result.reason);
            process.exitCode = 1;
          }
        }
      })();
    }
    return stopping;
  }
  for (const [signal, code] of [["SIGINT", 130], ["SIGTERM", 143]]) {
    process.on(signal, () => {
      if (stopping) return;
      process.exitCode = code;
      void stop();
    });
  }

  try {
    const contexts = [];
    for (const options of builds) {
      if (stopping) break;
      const pending = context(options);
      pendingContexts.push(pending);
      contexts.push(await pending);
    }
    if (!stopping) await Promise.all(contexts.map(item => item.rebuild()));
    if (!stopping) {
      await Promise.all(contexts.map(item => item.watch()));
      if (!stopping) console.log("[watch] Watching frontend sources");
    }
  } catch (error) {
    if (!stopping) {
      console.error("[watch] Failed to start:", error);
      process.exitCode = 1;
      await stop();
    }
  }
}
