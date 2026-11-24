// Telehealth call page. The room name and home URL come from data-* on #telehealth-config;
// the server decides whether this user may join the room.
document.addEventListener('DOMContentLoaded', function () {
    const cfg = document.getElementById('telehealth-config').dataset;
    const socket = window.socket || (typeof io === 'function' ? io() : null);
    const errorBox = document.getElementById('telehealth-error');
    const statusEl = document.getElementById('telehealth-status');
    const localVideo = document.getElementById('local-video');
    const remoteVideo = document.getElementById('remote-video');
    const muteAudioBtn = document.getElementById('mute-audio');
    const muteVideoBtn = document.getElementById('mute-video');
    const endCallBtn = document.getElementById('end-call');
    const room = cfg.room;
    const JOIN_FAILED = 'You cannot join this session. Go back and open it from your dashboard.';

    // iceServers: STUN only. There is no TURN relay, so video can fail behind strict firewalls.
    const configuration = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ]
    };

    let localStream = null;
    let peerConnection = null;

    function setStatus(text) { statusEl.textContent = text; }
    function showError(msg) {
        errorBox.textContent = msg;
        errorBox.hidden = false;
    }
    function clearError() { errorBox.hidden = true; }

    if (!socket) {
        showError('The connection to the server could not start. Reload the page.');
        return;
    }

    // 1. Get local media, then join the room.
    navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        .then(function (stream) {
            localStream = stream;
            localVideo.srcObject = stream;
            socket.emit('join', { room: room }, function (resp) {
                if (resp && (resp.error || resp.ok === false)) {
                    showError(JOIN_FAILED);
                    setStatus('Disconnected');
                } else {
                    setStatus('Waiting for the other person');
                }
            });
        })
        .catch(function () {
            showError('Could not use your camera and microphone. Allow them in your browser settings, then reload this page.');
            setStatus('Disconnected');
        });

    socket.on('join_error', function () {
        showError(JOIN_FAILED);
        setStatus('Disconnected');
    });

    // 2. Signalling.
    socket.on('ready', function () {
        if (!localStream) return;
        createPeerConnection();
        peerConnection.createOffer()
            .then(function (offer) { return peerConnection.setLocalDescription(offer); })
            .then(function () { socket.emit('offer', { offer: peerConnection.localDescription, room: room }); })
            .catch(function () { showError('Could not start the call. Reload the page and try again.'); });
    });

    socket.on('offer', function (data) {
        if (!localStream) return;
        createPeerConnection();
        peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer))
            .then(function () { return peerConnection.createAnswer(); })
            .then(function (answer) { return peerConnection.setLocalDescription(answer); })
            .then(function () { socket.emit('answer', { answer: peerConnection.localDescription, room: room }); })
            .catch(function () { showError('Could not answer the call. Reload the page and try again.'); });
    });

    socket.on('answer', function (data) {
        if (!peerConnection) return;
        peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer)).catch(function () {});
    });

    socket.on('candidate', function (data) {
        if (!peerConnection) return;
        peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate)).catch(function () {});
    });

    socket.on('_disconnect', function () {
        closePeer();
        remoteVideo.srcObject = null;
        setStatus('Disconnected');
    });

    function closePeer() {
        if (peerConnection) {
            peerConnection.close();
            peerConnection = null;
        }
    }

    // 3. Peer connection.
    function createPeerConnection() {
        if (peerConnection) return;
        peerConnection = new RTCPeerConnection(configuration);
        setStatus('Connecting');

        peerConnection.onicecandidate = function (event) {
            if (event.candidate) socket.emit('candidate', { candidate: event.candidate, room: room });
        };
        peerConnection.ontrack = function (event) {
            remoteVideo.srcObject = event.streams[0];
        };
        peerConnection.onconnectionstatechange = function () {
            if (!peerConnection) return;
            const state = peerConnection.connectionState;
            if (state === 'connected') {
                clearError();
                setStatus('Connected');
            } else if (state === 'failed') {
                setStatus('Disconnected');
                showError('Video could not connect. Some networks block direct video calls. Try another network or mobile data.');
            } else if (state === 'disconnected' || state === 'closed') {
                setStatus('Disconnected');
            }
        };
        localStream.getTracks().forEach(function (track) { peerConnection.addTrack(track, localStream); });
    }

    // 4. Controls. aria-pressed is true while the device is switched off.
    function toggle(btn, kind, onText, offText) {
        const tracks = localStream && (kind === 'audio' ? localStream.getAudioTracks() : localStream.getVideoTracks());
        const track = tracks && tracks[0];
        if (!track) return;
        track.enabled = !track.enabled;
        btn.setAttribute('aria-pressed', String(!track.enabled));
        btn.querySelector('[data-state]').textContent = track.enabled ? onText : offText;
    }
    muteAudioBtn.addEventListener('click', function () { toggle(muteAudioBtn, 'audio', 'Microphone on', 'Microphone off'); });
    muteVideoBtn.addEventListener('click', function () { toggle(muteVideoBtn, 'video', 'Camera on', 'Camera off'); });

    function leaveCall() {
        if (localStream) localStream.getTracks().forEach(function (t) { t.stop(); });
        closePeer();
        socket.emit('leave', { room: room });
        window.location.href = cfg.homeUrl;
    }

    endCallBtn.addEventListener('click', function () {
        if (window.MFH && typeof MFH.confirm === 'function') {
            MFH.confirm({
                title: 'Leave this call?',
                message: endCallBtn.dataset.confirm,
                confirmText: 'Leave call',
                danger: true
            }).then(function (ok) { if (ok) leaveCall(); });
        } else {
            leaveCall();
        }
    });

    window.addEventListener('beforeunload', function () {
        socket.emit('leave', { room: room });
    });
});
