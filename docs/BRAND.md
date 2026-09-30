# Clippi-Health brand

**Clippi-Health** is the public product and distribution name. The existing `hp` command, `healthpilot.py` builder, `healthpilot-source.json` metadata filename, and `hp://` desktop protocol remain stable compatibility interfaces.

## Logo candidates

The three transparent PNG masters are 1254 × 1254 pixels. **Record Smile is the selected direction**, revised with a clearer paperclip and more balanced cards. Its production master is also stored at [`assets/clippi-health-logo.png`](../assets/clippi-health-logo.png) and is used by the desktop app.

### 1. Heart Clip

![Heart Clip candidate](../assets/logo-candidates/01-heart-clip.png)

A paperclip flows into a heart and pulse. This is the clearest health-records concept and has the strongest small-icon silhouette.

### 2. Record Smile

![Record Smile candidate](../assets/logo-candidates/02-record-smile.png)

A clearly defined satin-metal paperclip holds friendly record cards. This is the selected direction: playful and approachable while the clip remains visually separate from the blue and aqua record artwork at app-icon scale.

### 3. Data Sprout

![Data Sprout candidate](../assets/logo-candidates/03-data-sprout.png)

A continuous clip orbits a small data sprout. This direction emphasizes personal growth, useful data, and a privacy boundary.

## Production

Derive the macOS `.icns`, Windows `.ico`, Linux PNG set, installer artwork, and favicon from the production master. The Electron header uses the master PNG, and its macOS startup sets the Dock icon explicitly so development launches do not retain Electron's placeholder. The generated standalone dashboard embeds the compact icon PNG so the logo remains visible offline and inside the packaged app. Keep the original proportions, transparent canvas, and enough clear space for rounded platform masks.
