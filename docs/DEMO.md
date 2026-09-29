# Recording a demo with Sally Seastar

Select **Try demo** in the desktop app header. Wait for **Demo · Sally Seastar** before starting your recording. The app creates a separate local record store with entirely fictional data; it does not copy, anonymize or read your own records.

The sample includes a year of simulated five-minute glucose readings, daily glucose mean/min/max and time in range, insulin and carbohydrate totals, sleep, steps, weight, blood pressure and heart metrics. Nine quarterly lab panels, visit notes, diagnoses, medications, immunizations, allergies, screening reports and journal entries fill out the other screens. Sally, her clinician and her clinic are fictional. These examples are not clinical advice or a validated simulation of diabetes physiology.

## A short walkthrough

1. Start at **Dashboard → Overview**. Click a timeline event and a topic.
2. Open **Labs**, select A1c or glucose, and compare the quarterly results.
3. Open **Vitals**. Drag across a glucose chart to zoom; double-click to reset. Try the date-range controls and scroll to insulin, carbohydrates, sleep and steps. The charts show daily summaries, not the individual five-minute samples.
4. Open **Records**, search for “diabetes,” and open a visit note.
5. Explore the desktop **Sources**, **Build**, **Timeline events**, **Notes** and **Doctor** tabs. Rebuilding and editing demo notes/events work normally within the sample store.
6. Stop recording, then select **Exit demo** and confirm that you want to show your personal records.

Demo mode persists across restarts. A full screen reload clears the previous record's cached panels and log when switching. The personal data-folder selection is retained and restored on exit. If preparing the demo fails, the previous record remains selected behind a privacy cover until you explicitly return or retry. Switching is refused while another operation is running.

Real file pickers, provider sign-ins, source configuration, data-folder changes and external windows are disabled in demo mode, including at the IPC boundary. Paths containing the operating-system username are not shown in the demo shell or log. Provider instructions can still be expanded and read. A separate browser or Tailscale dashboard you already opened continues to display its own data; demo mode changes only this desktop app's selected store. Record the app window rather than other windows or the whole desktop.

Keep manual edits fictional. Rebuilding preserves demo edits; exiting and starting another demo regenerates the supplied samples and recent dates. The demo is stored in `demo-records-v1` inside the app's local application-data directory. A missing demo store never falls back to personal records automatically.

## Development and verification

`demo_data.py` generates deterministic, seeded sample FHIR and HealthKit inputs and uses the regular builder, query engine and dashboard. It accepts only an empty directory or a store with its own demo marker and refuses symbolic links. The packaged runtime includes the same generator; installed users need no terminal or extra runtime.

Python integration tests exercise the populated import/build/search path. Desktop tests cover mode persistence, restoration, failed preparation, concurrent-operation guards and blocked personal-data actions. `npm run smoke` uses a disposable application profile, clicks **Try demo**, captures every desktop tab, and verifies populated lab/CGM charts and Plotly zoom. It never uses the developer's selected record store. Packaging checks also build and query the demo using the bundled native engine.
