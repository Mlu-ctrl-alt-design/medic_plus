// ICD-10-ZA picker — thin wrapper over MCodePicker. Kept as a separate
// component so existing call sites (`<MIcd10Picker …/>`) keep working.

function MIcd10Picker(props) {
  if (!window.MCodePicker) {
    return null;
  }
  return (
    <window.MCodePicker
      endpoint="medic_plus.api.daystar_health.search_icd10"
      placeholder={props.placeholder || 'Search ICD-10…'}
      emptyText="No matching ICD-10 codes."
      testid="icd10-picker"
      {...props}
    />
  );
}

window.MIcd10Picker = MIcd10Picker;
