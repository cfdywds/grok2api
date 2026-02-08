(() => {
  let Room;
  let createLocalTracks;
  let RoomEvent;
  let Track;
  let room = null;
  let visualizerTimer = null;
  let displayStream = null; // 用于存储屏幕共享音频流
  let audioContext = null; // Web Audio API 上下文
  let mixedStream = null; // 混合后的音频流
  let micGainNode = null; // 麦克风增益节点
  let tabGainNode = null; // 标签页音频增益节点

  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const statusText = document.getElementById('statusText');
  const logContainer = document.getElementById('log');
  const voiceSelect = document.getElementById('voiceSelect');
  const personalitySelect = document.getElementById('personalitySelect');
  const speedRange = document.getElementById('speedRange');
  const speedValue = document.getElementById('speedValue');
  const statusVoice = document.getElementById('statusVoice');
  const statusPersonality = document.getElementById('statusPersonality');
  const statusSpeed = document.getElementById('statusSpeed');
  const audioRoot = document.getElementById('audioRoot');
  const copyLogBtn = document.getElementById('copyLogBtn');
  const clearLogBtn = document.getElementById('clearLogBtn');
  const visualizer = document.getElementById('visualizer');
  const micSource = document.getElementById('micSource');
  const tabSource = document.getElementById('tabSource');
  const micVolume = document.getElementById('micVolume');
  const tabVolume = document.getElementById('tabVolume');
  const micVolumeValue = document.getElementById('micVolumeValue');
  const tabVolumeValue = document.getElementById('tabVolumeValue');
  const micVolumeControl = document.getElementById('micVolumeControl');
  const tabVolumeControl = document.getElementById('tabVolumeControl');

  function log(message, level = 'info') {
    if (!logContainer) {
      return;
    }
    const p = document.createElement('p');
    const time = new Date().toLocaleTimeString();
    p.textContent = `[${time}] ${message}`;
    if (level === 'error') {
      p.classList.add('log-error');
    } else if (level === 'warn') {
      p.classList.add('log-warn');
    }
    logContainer.prepend(p);
    if (typeof console !== 'undefined') {
      console.log(message);
    }
  }

  function toast(message, type) {
    if (typeof showToast === 'function') {
      showToast(message, type);
    } else {
      log(message, type === 'error' ? 'error' : 'info');
    }
  }

  function setStatus(state, text) {
    if (!statusText) {
      return;
    }
    statusText.textContent = text;
    statusText.classList.remove('connected', 'connecting', 'error');
    if (state) {
      statusText.classList.add(state);
    }
  }

  function setButtons(connected) {
    if (!startBtn || !stopBtn) {
      return;
    }
    if (connected) {
      startBtn.classList.add('hidden');
      stopBtn.classList.remove('hidden');
    } else {
      startBtn.classList.remove('hidden');
      stopBtn.classList.add('hidden');
      startBtn.disabled = false;
    }
  }

  function updateMeta() {
    if (statusVoice) {
      statusVoice.textContent = voiceSelect.value;
    }
    if (statusPersonality) {
      statusPersonality.textContent = personalitySelect.value;
    }
    if (statusSpeed) {
      statusSpeed.textContent = `${speedRange.value}x`;
    }
  }

  function initLiveKit() {
    const lk = window.LiveKitClient || window.LivekitClient;
    if (!lk) {
      return false;
    }
    Room = lk.Room;
    createLocalTracks = lk.createLocalTracks;
    RoomEvent = lk.RoomEvent;
    Track = lk.Track;
    return true;
  }

  function ensureLiveKit() {
    if (Room) {
      return true;
    }
    if (!initLiveKit()) {
      log('错误: LiveKit SDK 未能正确加载，请刷新页面重试', 'error');
      toast('LiveKit SDK 加载失败', 'error');
      return false;
    }
    return true;
  }

  function ensureMicSupport() {
    const hasMediaDevices = typeof navigator !== 'undefined' && navigator.mediaDevices;
    const hasGetUserMedia = hasMediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function';
    if (hasGetUserMedia) {
      return true;
    }
    const isLocalhost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
    const secureHint = window.isSecureContext || isLocalhost
      ? '请使用最新版浏览器并允许麦克风权限'
      : '请使用 HTTPS 或在本机 localhost 访问';
    throw new Error(`当前环境不支持麦克风权限，${secureHint}`);
  }

  async function startSession() {
    if (!ensureLiveKit()) {
      return;
    }

    try {
      const apiKey = await ensureApiKey();
      if (apiKey === null) {
        toast('请先登录后台', 'error');
        return;
      }

      startBtn.disabled = true;
      updateMeta();
      setStatus('connecting', '正在连接');
      log('正在获取 Token...');

      const params = new URLSearchParams({
        voice: voiceSelect.value,
        personality: personalitySelect.value,
        speed: speedRange.value
      });

      const headers = buildAuthHeaders(apiKey);

      const response = await fetch(`/api/v1/admin/voice/token?${params.toString()}`, {
        headers
      });

      if (!response.ok) {
        throw new Error(`获取 Token 失败: ${response.status}`);
      }

      const { token, url } = await response.json();
      log(`获取 Token 成功 (${voiceSelect.value}, ${personalitySelect.value}, ${speedRange.value}x)`);

      room = new Room({
        adaptiveStream: true,
        dynacast: true
      });

      room.on(RoomEvent.ParticipantConnected, (p) => log(`参与者已连接: ${p.identity}`));
      room.on(RoomEvent.ParticipantDisconnected, (p) => log(`参与者已断开: ${p.identity}`));
      room.on(RoomEvent.TrackSubscribed, (track) => {
        log(`订阅音轨: ${track.kind}`);
        if (track.kind === Track.Kind.Audio) {
          const element = track.attach();
          if (audioRoot) {
            audioRoot.appendChild(element);
          } else {
            document.body.appendChild(element);
          }
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        log('已断开连接');
        resetUI();
      });

      await room.connect(url, token);
      log('已连接到 LiveKit 服务器');

      setStatus('connected', '通话中');
      setButtons(true);

      // 根据选择的音频源类型开启不同的音频输入
      const useTabAudio = tabSource && tabSource.checked;
      const useMicAudio = micSource && micSource.checked;

      log(`音频源选择: 麦克风=${useMicAudio}, 标签页=${useTabAudio}`);

      // 如果两个都没选中，提示用户
      if (!useTabAudio && !useMicAudio) {
        log('请至少选择一个音频源（麦克风或标签页音频）', 'warn');
        toast('请选择音频源', 'warning');
        return;
      }

      // 收集所有音频源
      const audioSources = [];

      // 获取标签页音频
      if (useTabAudio) {
        log('正在请求浏览器标签页音频...');
        try {
          displayStream = await navigator.mediaDevices.getDisplayMedia({
            video: {
              width: { ideal: 1 },
              height: { ideal: 1 },
              frameRate: { ideal: 1 }
            },
            audio: {
              echoCancellation: false,
              noiseSuppression: false,
              autoGainControl: false
            }
          });

          const audioTracks = displayStream.getAudioTracks();
          if (audioTracks.length === 0) {
            throw new Error('未能获取到标签页音频，请确保选择了包含音频的标签页并勾选"共享标签页音频"');
          }

          log(`已获取标签页音频: ${audioTracks[0].label}`);
          audioSources.push({ track: audioTracks[0], name: '标签页音频' });

          // 停止视频轨道
          const videoTracks = displayStream.getVideoTracks();
          videoTracks.forEach(track => {
            track.stop();
            displayStream.removeTrack(track);
          });

          // 监听音频轨道结束事件
          audioTracks[0].addEventListener('ended', () => {
            log('标签页音频共享已停止', 'warn');
            toast('音频共享已停止', 'warning');
          });

        } catch (err) {
          log(`获取标签页音频失败: ${err.message}`, 'error');

          let errorMsg = '获取标签页音频失败';
          if (err.name === 'NotAllowedError') {
            errorMsg = '用户拒绝了音频共享请求';
          } else if (err.name === 'NotSupportedError') {
            errorMsg = '当前浏览器不支持标签页音频捕获，请使用 Chrome 或 Edge 浏览器';
          } else if (err.message.includes('audio')) {
            errorMsg = '请在共享时勾选"共享标签页音频"选项';
          }

          toast(errorMsg, 'error');
          throw new Error(errorMsg);
        }
      }

      // 获取麦克风音频
      if (useMicAudio) {
        log('正在开启麦克风...');
        try {
          ensureMicSupport();
          const micStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: false
          });
          const micTrack = micStream.getAudioTracks()[0];
          log(`已获取麦克风: ${micTrack.label}`);
          audioSources.push({ track: micTrack, name: '麦克风', isNative: true });
        } catch (err) {
          log(`开启麦克风失败: ${err.message}`, 'error');
          toast('麦克风开启失败', 'error');
          if (audioSources.length === 0) {
            throw new Error('无可用音频源');
          }
        }
      }

      // 如果只有一个音频源，直接发布
      if (audioSources.length === 1) {
        log(`使用单一音频源: ${audioSources[0].name}`);

        // 如果是单一麦克风，使用 LiveKit 的 createLocalTracks 方法
        if (audioSources[0].name === '麦克风' && audioSources[0].isNative) {
          log('使用 LiveKit createLocalTracks 创建麦克风轨道...');
          // 停止之前获取的原生轨道
          audioSources[0].track.stop();
          // 使用 LiveKit 标准方法创建轨道
          const tracks = await createLocalTracks({ audio: true, video: false });
          for (const track of tracks) {
            await room.localParticipant.publishTrack(track);
            log(`已发布音频轨道: ${track.kind}`);
          }
          log('麦克风已开启，AI 正在监听...');
          toast('语音连接成功', 'success');
        }
        // 如果是标签页音频，直接发布原生轨道
        else {
          const publication = await room.localParticipant.publishTrack(audioSources[0].track, {
            name: 'tab-audio'
          });
          log(`已发布音频轨道: trackSid=${publication.trackSid}`);
          log(`${audioSources[0].name}已开启，AI 正在监听...`);
          toast('音频连接成功', 'success');
        }
      }
      // 如果有多个音频源，混合后发布
      else if (audioSources.length > 1) {
        log(`检测到 ${audioSources.length} 个音频源，正在混合...`);

        try {
          // 创建 Web Audio API 上下文，使用标准采样率
          audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 48000,  // 使用 48kHz 采样率，LiveKit 标准
            latencyHint: 'interactive'  // 低延迟模式
          });

          log(`AudioContext 创建成功: sampleRate=${audioContext.sampleRate}Hz`);

          // 创建混音器
          const destination = audioContext.createMediaStreamDestination();

          // 将所有音频源连接到混音器
          for (const source of audioSources) {
            const mediaStream = new MediaStream([source.track]);
            const sourceNode = audioContext.createMediaStreamSource(mediaStream);

            // 添加增益节点，可以调整音量
            const gainNode = audioContext.createGain();

            // 根据音频源类型设置初始音量
            if (source.name === '麦克风') {
              const micVol = micVolume ? parseInt(micVolume.value) / 100 : 1.0;
              gainNode.gain.value = micVol;
              micGainNode = gainNode;
              log(`麦克风音量设置: ${Math.round(micVol * 100)}%`);
            } else if (source.name === '标签页音频') {
              const tabVol = tabVolume ? parseInt(tabVolume.value) / 100 : 0.3;
              gainNode.gain.value = tabVol;
              tabGainNode = gainNode;
              log(`标签页音频音量设置: ${Math.round(tabVol * 100)}%`);
            } else {
              gainNode.gain.value = 1.0;
            }

            sourceNode.connect(gainNode);
            gainNode.connect(destination);

            log(`已添加音频源到混音器: ${source.name} (sampleRate=${source.track.getSettings().sampleRate}Hz)`);
          }

          // 获取混合后的音频轨道
          mixedStream = destination.stream;
          const mixedTrack = mixedStream.getAudioTracks()[0];

          log(`音频混合完成: ${mixedTrack.label}, readyState=${mixedTrack.readyState}`);
          log(`正在发布混合轨道...`);

          // 直接发布混合轨道
          const publication = await room.localParticipant.publishTrack(mixedTrack, {
            name: 'mixed-audio',
            audioBitrate: 64000  // 设置音频比特率
          });

          log(`已发布混合音频轨道: trackSid=${publication.trackSid}`);
          log('所有音频源已混合并开启，AI 正在监听...');
          log('提示: 可以在会话中实时调整音量滑块');
          toast('多音频源混合成功，可实时调整音量', 'success');

        } catch (err) {
          log(`音频混合失败: ${err.message}`, 'error');
          toast('音频混合失败，请尝试单独使用一个音频源', 'error');
          throw err;
        }
      }

      // 输出当前房间的所有本地轨道信息
      log(`当前本地轨道数量: ${room.localParticipant.trackPublications.size}`);
      room.localParticipant.trackPublications.forEach((pub, sid) => {
        log(`  - ${pub.kind} 轨道: ${pub.trackName}, sid=${sid}, muted=${pub.isMuted}`);
      });
    } catch (err) {
      const message = err && err.message ? err.message : '连接失败';
      log(`错误: ${message}`, 'error');
      toast(message, 'error');
      setStatus('error', '连接错误');
      startBtn.disabled = false;
    }
  }

  async function stopSession() {
    if (room) {
      await room.disconnect();
    }
    // 停止屏幕共享音频流
    if (displayStream) {
      displayStream.getTracks().forEach(track => track.stop());
      displayStream = null;
      log('已停止标签页音频捕获');
    }
    // 停止混合音频流
    if (mixedStream) {
      mixedStream.getTracks().forEach(track => track.stop());
      mixedStream = null;
      log('已停止混合音频流');
    }
    // 关闭 Audio Context
    if (audioContext) {
      await audioContext.close();
      audioContext = null;
      log('已关闭音频上下文');
    }
    // 重置增益节点
    micGainNode = null;
    tabGainNode = null;
    resetUI();
  }

  function resetUI() {
    setStatus('', '未连接');
    setButtons(false);
    if (audioRoot) {
      audioRoot.innerHTML = '';
    }
  }

  function clearLog() {
    if (logContainer) {
      logContainer.innerHTML = '';
    }
  }

  async function copyLog() {
    if (!logContainer) {
      return;
    }
    const lines = Array.from(logContainer.querySelectorAll('p'))
      .map((p) => p.textContent)
      .join('\n');
    try {
      await navigator.clipboard.writeText(lines);
      toast('日志已复制', 'success');
    } catch (err) {
      toast('复制失败，请手动选择', 'error');
    }
  }

  speedRange.addEventListener('input', (e) => {
    speedValue.textContent = Number(e.target.value).toFixed(1);
    const min = Number(speedRange.min || 0);
    const max = Number(speedRange.max || 100);
    const val = Number(speedRange.value || 0);
    const pct = ((val - min) / (max - min)) * 100;
    speedRange.style.setProperty('--range-progress', `${pct}%`);
    updateMeta();
  });

  // 麦克风音量控制
  if (micVolume) {
    micVolume.addEventListener('input', (e) => {
      const value = parseInt(e.target.value);
      if (micVolumeValue) {
        micVolumeValue.textContent = value;
      }
      // 实时调整增益
      if (micGainNode) {
        micGainNode.gain.value = value / 100;
        log(`麦克风音量调整为: ${value}%`);
      }
    });
  }

  // 标签页音频音量控制
  if (tabVolume) {
    tabVolume.addEventListener('input', (e) => {
      const value = parseInt(e.target.value);
      if (tabVolumeValue) {
        tabVolumeValue.textContent = value;
      }
      // 实时调整增益
      if (tabGainNode) {
        tabGainNode.gain.value = value / 100;
        log(`标签页音频音量调整为: ${value}%`);
      }
    });
  }

  // 音频源选择变化时显示/隐藏音量控制
  if (micSource) {
    micSource.addEventListener('change', (e) => {
      if (micVolumeControl) {
        if (e.target.checked && tabSource && tabSource.checked) {
          micVolumeControl.classList.remove('hidden');
        } else {
          micVolumeControl.classList.add('hidden');
        }
      }
    });
  }

  if (tabSource) {
    tabSource.addEventListener('change', (e) => {
      if (tabVolumeControl) {
        if (e.target.checked && micSource && micSource.checked) {
          tabVolumeControl.classList.remove('hidden');
        } else {
          tabVolumeControl.classList.add('hidden');
        }
      }
      // 同时更新麦克风音量控制的显示
      if (micVolumeControl && micSource) {
        if (e.target.checked && micSource.checked) {
          micVolumeControl.classList.remove('hidden');
        } else {
          micVolumeControl.classList.add('hidden');
        }
      }
    });
  }

  voiceSelect.addEventListener('change', updateMeta);
  personalitySelect.addEventListener('change', updateMeta);

  startBtn.addEventListener('click', startSession);
  stopBtn.addEventListener('click', stopSession);
  if (copyLogBtn) {
    copyLogBtn.addEventListener('click', copyLog);
  }
  if (clearLogBtn) {
    clearLogBtn.addEventListener('click', clearLog);
  }

  speedValue.textContent = Number(speedRange.value).toFixed(1);
  {
    const min = Number(speedRange.min || 0);
    const max = Number(speedRange.max || 100);
    const val = Number(speedRange.value || 0);
    const pct = ((val - min) / (max - min)) * 100;
    speedRange.style.setProperty('--range-progress', `${pct}%`);
  }
  function buildVisualizerBars() {
    if (!visualizer) return;
    visualizer.innerHTML = '';
    const targetCount = Math.max(36, Math.floor(visualizer.offsetWidth / 7));
    for (let i = 0; i < targetCount; i += 1) {
      const bar = document.createElement('div');
      bar.className = 'bar';
      visualizer.appendChild(bar);
    }
  }

  window.addEventListener('resize', buildVisualizerBars);
  buildVisualizerBars();
  updateMeta();
  setStatus('', '未连接');

  if (!visualizerTimer) {
    visualizerTimer = setInterval(() => {
      const bars = document.querySelectorAll('.visualizer .bar');
      bars.forEach((bar) => {
        if (statusText && statusText.classList.contains('connected')) {
          bar.style.height = `${Math.random() * 32 + 6}px`;
        } else {
          bar.style.height = '6px';
        }
      });
    }, 150);
  }
})();
