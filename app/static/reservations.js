// Toggle edit mode and cancel selected reservations on My reservations.
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var list = document.getElementById('reservation-list');
    var toggle = document.getElementById('reservation-edit-toggle');
    var form = document.getElementById('reservation-cancel-form');
    if (!list || !toggle || !form) {
      return;
    }

    var checkboxes = Array.prototype.slice.call(
      form.querySelectorAll('.reservation-select')
    );
    var cancelButton = document.getElementById('reservation-cancel-button');

    function selectedCount() {
      return checkboxes.filter(function (box) {
        return box.checked;
      }).length;
    }

    function refresh() {
      var count = selectedCount();
      list.classList.toggle('has-selection', count > 0);
      cancelButton.disabled = count === 0;
      cancelButton.textContent = count
        ? 'Cancel selected (' + count + ')'
        : 'Cancel selected';
    }

    toggle.addEventListener('click', function () {
      var editing = list.classList.toggle('is-editing');
      toggle.setAttribute('aria-pressed', String(editing));
      toggle.textContent = editing ? 'Done' : '✎ Edit';
      if (!editing) {
        checkboxes.forEach(function (box) {
          box.checked = false;
        });
      }
      refresh();
    });

    checkboxes.forEach(function (box) {
      box.addEventListener('change', refresh);
    });

    form.addEventListener('submit', function (event) {
      var count = selectedCount();
      if (count === 0) {
        event.preventDefault();
        return;
      }
      if (!window.confirm('Cancel ' + count + ' selected reservation(s)?')) {
        event.preventDefault();
      }
    });

    refresh();
  });
})();
