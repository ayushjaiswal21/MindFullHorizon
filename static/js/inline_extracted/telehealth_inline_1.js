
    document.addEventListener('DOMContentLoaded', function() {
        const socket = io();
        const localVideo = document.getElementById('local-video');
        const remoteVideo = document.getElementById('remote-video');
        const muteAudioBtn = document.getElementById('mute-audio');
        const muteVideoBtn = document.getElementById('mute-video');
        const endCallBtn = document.getElementById('end-call');

        let localStream;
        let peerConnection;
        const room = 'telehealth_room_{{ patient_id }}'; // Use patient_id for room name

        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };

        // 1. Get local media and join room
        navigator.mediaDevices.getUserMedia({ video: true, audio: true })
            .then(stream => {
                localStream = stream;
                localVideo.srcObject = stream;
                socket.emit('join', { room: room });
            })
            .catch(error => {
                console.error('Error accessing media devices.', error);
                alert('Could not access camera/microphone. Please ensure they are enabled.');
            });

        // 2. Socket.IO event handlers
        socket.on('ready', () => {
            console.log('Socket is ready, creating offer...');
            createPeerConnection();
            peerConnection.createOffer()
                .then(offer => peerConnection.setLocalDescription(offer))
                .then(() => {
                    socket.emit('offer', { offer: peerConnection.localDescription, room: room });
                })
                .catch(error => console.error('Error creating offer:', error));
        });

        socket.on('offer', (data) => {
            console.log('Received offer, creating answer...');
            createPeerConnection();
            peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer))
                .then(() => peerConnection.createAnswer())
                .then(answer => peerConnection.setLocalDescription(answer))
                .then(() => {
                    socket.emit('answer', { answer: peerConnection.localDescription, room: room });
                })
                .catch(error => console.error('Error creating answer:', error));
        });

        socket.on('answer', (data) => {
            console.log('Received answer.');
            peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer))
                .catch(error => console.error('Error setting remote description (answer):', error));
        });

        socket.on('candidate', (data) => {
            console.log('Received ICE candidate.');
            peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate))
                .catch(error => console.error('Error adding ICE candidate:', error));
        });

        socket.on('_disconnect', () => {
            console.log('Peer disconnected.');
            if (peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            remoteVideo.srcObject = null;
            alert('The other participant has disconnected.');
        });

        // 3. WebRTC Peer Connection setup
        function createPeerConnection() {
            if (peerConnection) return;
            peerConnection = new RTCPeerConnection(configuration);

            peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    socket.emit('candidate', { candidate: event.candidate, room: room });
                }
            };

            peerConnection.ontrack = (event) => {
                console.log('Remote stream added.', event.streams[0]);
                remoteVideo.srcObject = event.streams[0];
            };

            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
        }

        // UI Button Handlers
        muteAudioBtn.addEventListener('click', () => {
            const audioTrack = localStream.getAudioTracks()[0];
            if (audioTrack) {
                audioTrack.enabled = !audioTrack.enabled;
                muteAudioBtn.classList.toggle('bg-red-600');
                muteAudioBtn.classList.toggle('bg-green-600');
                muteAudioBtn.innerHTML = audioTrack.enabled ? '<i class="fas fa-microphone"></i>' : '<i class="fas fa-microphone-slash"></i>';
            }
        });

        muteVideoBtn.addEventListener('click', () => {
            const videoTrack = localStream.getVideoTracks()[0];
            if (videoTrack) {
                videoTrack.enabled = !videoTrack.enabled;
                muteVideoBtn.classList.toggle('bg-red-600');
                muteVideoBtn.classList.toggle('bg-green-600');
                muteVideoBtn.innerHTML = videoTrack.enabled ? '<i class="fas fa-video"></i>' : '<i class="fas fa-video-slash"></i>';
            }
        });

        endCallBtn.addEventListener('click', () => {
            if (localStream) {
                localStream.getTracks().forEach(track => track.stop());
            }
            if (peerConnection) {
                peerConnection.close();
            }
            socket.emit('leave', { room: room });
            window.location.href = "{{ url_for('patient.patient_dashboard') if session.user_role == 'patient' else url_for('provider_dashboard') }}";
        });

        // Handle browser tab/window close
        window.addEventListener('beforeunload', () => {
            socket.emit('leave', { room: room });
        });
    });
