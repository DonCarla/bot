// ===== sofa_proxy.js =====
const express = require("express");
const cors = require("cors");
const fetch = (...args) =>
  import("node-fetch").then(({ default: fetch }) => fetch(...args));

const app = express();
app.use(cors());

const SOFA_URL = "https://www.sofascore.com/api/v1/sport/tennis/events/live";

app.get("/live", async (req, res) => {
  try {
    const response = await fetch(SOFA_URL, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.sofascore.com/",
      },
    });

    if (!response.ok) {
      console.log("❌ Sofascore error:", response.status);
      return res.status(response.status).json({ error: response.statusText });
    }

    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error("Proxy error:", err);
    res.status(500).json({ error: err.toString() });
  }
});

const PORT = 3000;
app.listen(PORT, () =>
  console.log(`✅ Sofascore proxy запущен на http://localhost:${PORT}/live`)
);
