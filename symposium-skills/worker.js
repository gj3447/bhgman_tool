// SYMPOSIUM Skills installer redirect — Cloudflare Worker.
// Routes:
//   metahumotonic.com/install     → install.sh
//   metahumotonic.com/install.sh  → install.sh
//   metahumotonic.com/uninstall   → uninstall.sh

const REPO = "airobotics-inc/symposium-skills";
const BRANCH = "main";
const RAW = `https://raw.githubusercontent.com/${REPO}/${BRANCH}`;

const ROUTES = {
  "/install":      `${RAW}/install.sh`,
  "/install.sh":   `${RAW}/install.sh`,
  "/uninstall":    `${RAW}/uninstall.sh`,
  "/uninstall.sh": `${RAW}/uninstall.sh`,
};

export default {
  async fetch(req) {
    const url = new URL(req.url);
    const target = ROUTES[url.pathname];
    if (target) {
      const upstream = await fetch(target, { cf: { cacheTtl: 60 } });
      return new Response(upstream.body, {
        status: upstream.status,
        headers: {
          "content-type": "text/x-shellscript; charset=utf-8",
          "cache-control": "public, max-age=60",
          "x-symposium-source": target,
        },
      });
    }
    return new Response(
      "SYMPOSIUM Skills — try /install or /uninstall\n" +
      "  curl -sSL https://install.metahumotonic.com/install | bash\n",
      { status: 404, headers: { "content-type": "text/plain; charset=utf-8" } }
    );
  },
};
