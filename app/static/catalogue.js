// Auto-fill copy location from the selected status on catalogue forms.
(function () {
  'use strict';

  function locationForStatus(status) {
    if (status === 'damaged' || status === 'under_repair') {
      return 'Repair room';
    }
    if (status === 'lost') {
      return 'Missing';
    }
    return ''; // available: the librarian enters a shelf location
  }

  function wire(select) {
    var targetId = select.getAttribute('data-location-target');
    if (!targetId) {
      return;
    }
    var input = document.getElementById(targetId);
    if (!input) {
      return;
    }
    select.addEventListener('change', function () {
      input.value = locationForStatus(select.value);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var selects = document.querySelectorAll('select[data-location-target]');
    for (var i = 0; i < selects.length; i += 1) {
      wire(selects[i]);
    }
  });
})();
