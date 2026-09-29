# Glucose and insulin together

**Dashboard → Vitals** starts with a paired diabetes view. Glucose appears on the left and insulin on the right. Both charts share the selected date window: dragging to zoom either chart updates the other, and double-clicking resets both. Narrow windows stack the panels vertically.

- **Blue:** CGM/meter glucose, with the daily mean and daily minimum/maximum band.
- **Pink:** basal insulin delivered per day.
- **Orange:** bolus insulin delivered per day.
- **Gray, dotted:** insulin with missing, conflicting or unrecognized delivery-type metadata.

The charts retain separate units: glucose in mg/dL and insulin in units delivered. Dense series also show a 30-day average. These are daily summaries, not a pump dosing screen or an intraday dose/glucose overlay. The feature displays imported delivery records; it does not add manual insulin logging or infer doses.

## Where the distinction comes from

Apple Health exports can include `HKInsulinDeliveryReason` metadata on insulin samples. The importer also accepts the SDK key spelling `HKMetadataKeyInsulinDeliveryReason`. The numeric values are 1 for basal and 2 for bolus. Missing or other values remain unspecified. Apple documents the [required metadata key](https://developer.apple.com/documentation/healthkit/hkmetadatakeyinsulindeliveryreason) and the [basal](https://developer.apple.com/documentation/healthkit/hkinsulindeliveryreason/basal) and [bolus](https://developer.apple.com/documentation/healthkit/hkinsulindeliveryreason/bolus) delivery reasons.

`vitals_daily` retains the existing `Insulin` combined total and adds `Insulin basal`, `Insulin bolus` and `Insulin unspecified`. Each day's breakdown comes from the same source selected for that day's combined total. As with the existing importer, the largest daily total among apps is selected to avoid adding duplicate feeds together; equal totals prefer the source with more classified insulin. This rule does not reconcile complementary insulin records spread across different apps. Rounding to tenths can make displayed component sums differ slightly from the rounded total.

Choose **Build → Rebuild now** to populate the breakdown from an existing export. The versioned device-data cache forces a fresh parse of older imports. Without a rebuilt breakdown, older totals remain visible as a dotted orange “Total · type unavailable” series. A missing category is not fabricated as a measured zero. The raw export is unchanged.

Sally Seastar's demo contains synthetic basal and bolus records so both colors and the linked charts can be demonstrated. Tests cover reason mapping, unspecified data, zero values, multiple source feeds, old cache invalidation, both chart themes and synchronized zoom/reset.
