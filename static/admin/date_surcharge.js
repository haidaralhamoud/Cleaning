(function () {
  function toggleFields() {
    var ruleType = document.getElementById('id_rule_type');
    var weekday = document.getElementById('id_weekday');
    var date = document.getElementById('id_date');

    if (!ruleType || (!weekday && !date)) return;

    var showWeekday = ruleType.value === 'weekday';
    var showDate = ruleType.value === 'date';

    if (weekday) {
      var weekdayRow = weekday.closest('.form-row') || weekday.closest('.form-group') || weekday.parentElement;
      if (weekdayRow) weekdayRow.style.display = showWeekday  '' : 'none';
    }
    if (date) {
      var dateRow = date.closest('.form-row') || date.closest('.form-group') || date.parentElement;
      if (dateRow) dateRow.style.display = showDate  '' : 'none';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var ruleType = document.getElementById('id_rule_type');
    if (!ruleType) return;
    toggleFields();
    ruleType.addEventListener('change', toggleFields);
  });
})();
