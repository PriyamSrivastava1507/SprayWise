# SprayWise frontend

Plain HTML, CSS and JavaScript (ES modules). No framework, no build step, no
`npm install`. It talks to the FastAPI backend and never does image analysis itself.

## Run it

1. Start the backend (see `backend/README.md`) on port 8000.
2. Serve this folder on port 5173, which the backend allows by default:

   ```bash
   cd frontend
   python -m http.server 5173
   ```

3. Open <http://localhost:5173>.

Opening `index.html` by double-clicking will not work: browsers block ES
modules from `file://`. If you use another port, add it to the backend's
`ALLOWED_ORIGINS`.

## Configuration

`js/config.js` holds everything that differs between a laptop and a server:
the API address, the upload limit (keep it equal to the backend's
`MAX_UPLOAD_MB`), and how money is formatted (`LOCALE`, `CURRENCY`; default
Indian rupees). The file is public, so never put secrets in it.

## Pages

| Route | What it does |
|---|---|
| `#/analyze` | Upload a photo, choose Classical, ML or Both, see where to spray and what it saves |
| `#/compare` | Runs both methods on one photo and shows them side by side |
| `#/history` | Scans per field, weed-cover trend, View / CSV / PDF / Delete |
| `#/scans/:id` | One stored scan |
| `#/evaluation` | Classical vs ML scores on the labelled test photos |

## Interactive tools

- **Map:** switch the crop, weed and spray-zone layers; zoom with + / − / Fit,
  Ctrl (or ⌘) + scroll, double-click or a two-finger pinch; drag to move;
  from the keyboard, focus the map and use + − 0 and the arrow keys. Hovering
  any map (and the two zone maps below it) shows the zone's row, column,
  weed share and whether it is sprayed.
- **Adjust and recalculate:** on a result, move the spray threshold or the zone
  grid, or change area, dose or price, and everything updates while you move
  the controls. Previews come from `POST /scans/{id}/recalculate?save=false`,
  so the numbers are the server's. Downloads are disabled until you
  **Save to scan**; **Reset** goes back to the saved settings.
- **Swipe comparison:** on Compare (and on a Both scan's page), drag the
  divider to see classical on the left and ML on the right over the same
  photo, each with its own spray zones. It needs a successful result from both
  methods; otherwise Side by side is shown.

## Structure

```
index.html            shell: top bar, <main id="app">, toasts
css/styles.css        the only stylesheet
js/config.js          settings
js/main.js            routes
js/router.js          hash router; pages export mount(root, params)
js/services/          api.js (fetch + ApiError), endpoints.js (one object per resource)
js/utils/             dom.js (h() builds elements with textContent), formatters, calculations
js/components/        states (loading/empty/error), toast, health badge
js/features/          analyze/, compare/, history/, evaluation/
```

## Rules the code follows

- Every result is checked by `status` first (`ok`, `rows_not_detected`,
  `model_unavailable`, `failed`); non-ok results show an explanation, never a crash.
- Numbers shown come from the API. The browser formats them; it does not
  recompute savings or statistics.
- `model_id == "fake-demo-model"` is always labelled **Demo model**.
- Text from the server is inserted with `textContent`, never `innerHTML`.
- The crop and weed layers are drawn from each result's `mask_url`, so they are
  exact. If the mask cannot be loaded, the finished overlay picture is shown.
- Weed pressure limits come from `/health` (`pressure_thresholds`).
- The form remembers its last values in `localStorage`; nothing else is stored.

## Testing checklist

With DevTools open (Console for errors, Network for each request):
analyze in each mode; a classical photo with no rows; an invalid file; a file
over the limit; `SEGMENTATION_BACKEND=unavailable` (ML gives 503, Both keeps
classical); stop the backend (badge shows API offline, actions explain);
History filter, trend, paging, delete; `#/scans/99999`; CSV and PDF downloads;
a 390 px wide window; keyboard-only use of the form.

## Deploy

Any static host works (Netlify, Vercel, GitHub Pages). Hash routing needs no
rewrite rules. Set `API_BASE` in `js/config.js` to the deployed backend and add
the site's address to the backend's `ALLOWED_ORIGINS`. There is no login in
this version.
