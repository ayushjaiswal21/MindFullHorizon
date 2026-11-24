/* Sign-up page: a non-empty counsellor invite code switches the hidden role to "provider".
   The server still checks the code; without JS the role stays "patient". */
(function () {
  'use strict';
  var invite = document.getElementById('invite_code');
  var role = document.getElementById('role');
  if (!invite || !role) return;
  function syncRole() { role.value = invite.value.trim() ? 'provider' : 'patient'; }
  invite.addEventListener('input', syncRole);
  if (invite.form) invite.form.addEventListener('submit', syncRole, true);
  syncRole();
})();
