# Third-party notices

Clippi-Health is licensed under Apache-2.0. Third-party software remains under
the licenses named below and is not relicensed by the Clippi-Health license.

## Plotly.js

Clippi-Health includes `vendor/plotly-basic.min.js`, the Plotly.js basic bundle
v4.1.1.

Copyright (c) 2016-2024 Plotly Technologies Inc.

Plotly.js is licensed under the MIT License. The complete license is included at
`vendor/LICENSE.plotly.js.txt`. App builds copy it to
`dist/LICENSE.plotly.js.txt`. Copyright and license notices for components
incorporated by Plotly's own build remain embedded in the minified bundle.

## Electron development and packaging dependencies

The optional desktop app's exact dependency versions and declared licenses are
recorded in `app/package-lock.json`. The source distribution does not contain
`node_modules`. App packages must preserve the licenses and notices that ship
with the Electron runtime and its bundled components, including Chromium, and
must be inspected before release as described in `DISTRIBUTION.md`.
