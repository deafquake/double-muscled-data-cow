import 'dart:async';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';
import '../services/video_storage_service.dart';
import '../services/video_upload_service.dart';

const _kSegmentDuration = Duration(minutes: 5);

class CameraScreen extends StatefulWidget {
  final List<CameraDescription> cameras;

  const CameraScreen({super.key, required this.cameras});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  late CameraController _controller;
  int _cameraIndex = 0;
  bool _isInitialized = false;
  bool _isRecording = false;
  bool _isSaving = false;
  Duration _elapsed = Duration.zero;
  Timer? _elapsedTimer;
  Timer? _segmentTimer;
  int _pendingUploads = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _initCamera(widget.cameras[_cameraIndex]);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    _elapsedTimer?.cancel();
    _segmentTimer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_controller.value.isInitialized) return;
    if (state == AppLifecycleState.inactive) {
      _controller.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initCamera(widget.cameras[_cameraIndex]);
    }
  }

  Future<void> _initCamera(CameraDescription camera) async {
    _controller = CameraController(
      camera,
      ResolutionPreset.high,
      enableAudio: true,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );

    try {
      await _controller.initialize();
      if (mounted) setState(() => _isInitialized = true);
    } on CameraException catch (e) {
      _showError('Camera error: ${e.description}');
    }
  }

  Future<void> _toggleRecording() async {
    if (_isRecording) {
      await _stopRecording();
    } else {
      await _startRecording();
    }
  }

  Future<void> _startRecording() async {
    try {
      await _controller.startVideoRecording();
      setState(() {
        _isRecording = true;
        _elapsed = Duration.zero;
      });
      _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() => _elapsed += const Duration(seconds: 1));
      });
      _segmentTimer = Timer.periodic(_kSegmentDuration, (_) {
        _rotateSegment();
      });
    } on CameraException catch (e) {
      _showError('Could not start recording: ${e.description}');
    }
  }

  /// Stops the current segment, uploads it in the background, then immediately
  /// starts the next segment — all without interrupting the user's recording session.
  Future<void> _rotateSegment() async {
    if (!mounted || !_isRecording || !_controller.value.isRecordingVideo) {
      return;
    }
    final apiUrl = context.read<SettingsProvider>().apiUrl;

    try {
      final xfile = await _controller.stopVideoRecording();
      await _controller.startVideoRecording();

      if (apiUrl.isNotEmpty) {
        _uploadSegment(xfile.path, apiUrl);
      } else {
        File(xfile.path).delete().ignore();
      }
    } on CameraException catch (e) {
      if (mounted) _showError('Segment rotation failed: ${e.description}');
    }
  }

  /// Fire-and-forget upload. Increments [_pendingUploads] while in flight.
  void _uploadSegment(String filePath, String apiUrl) {
    if (mounted) setState(() => _pendingUploads++);

    VideoUploadService(baseUrl: apiUrl)
        .uploadVideo(filePath)
        .then((_) => File(filePath).delete().ignore())
        .catchError((Object e) {
      if (mounted) _showError('Upload failed: $e');
    }).whenComplete(() {
      if (mounted) setState(() => _pendingUploads--);
    });
  }

  Future<void> _stopRecording() async {
    _elapsedTimer?.cancel();
    _segmentTimer?.cancel();

    // Capture context-dependent values before any awaits.
    final syncPath = context.read<SettingsProvider>().syncFolderPath;
    final apiUrl = context.read<SettingsProvider>().apiUrl;

    setState(() {
      _isRecording = false;
      _isSaving = true;
    });

    try {
      final recording = await _controller.stopVideoRecording();
      final saved = await VideoStorageService.saveRecording(recording, syncPath);

      if (apiUrl.isNotEmpty) {
        _uploadSegment(saved.path, apiUrl);
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Video saved to sync folder'),
            backgroundColor: Colors.green.shade700,
            duration: const Duration(seconds: 2),
          ),
        );
        Navigator.pop(context);
      }
    } on CameraException catch (e) {
      _showError('Could not save recording: ${e.description}');
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _switchCamera() async {
    if (widget.cameras.length < 2 || _isRecording) return;

    setState(() => _isInitialized = false);
    _cameraIndex = (_cameraIndex + 1) % widget.cameras.length;
    await _controller.dispose();
    await _initCamera(widget.cameras[_cameraIndex]);
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red.shade700),
    );
  }

  String _formatElapsed(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return h > 0 ? '$h:$m:$s' : '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Camera preview
          if (_isInitialized)
            CameraPreview(_controller)
          else
            const Center(child: CircularProgressIndicator(color: Colors.white)),

          // Top bar: close + timer + upload badge
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Close button (disabled while recording)
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white),
                      onPressed:
                          _isRecording ? null : () => Navigator.pop(context),
                    ),

                    // Recording timer + upload badge
                    if (_isRecording)
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.red.withValues(alpha: 0.85),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.circle,
                                    color: Colors.white, size: 10),
                                const SizedBox(width: 6),
                                Text(
                                  _formatElapsed(_elapsed),
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 16,
                                    fontFeatures: [
                                      FontFeature.tabularFigures()
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (_pendingUploads > 0) ...[
                            const SizedBox(width: 8),
                            _UploadBadge(count: _pendingUploads),
                          ],
                        ],
                      ),

                    // Switch camera
                    IconButton(
                      icon: const Icon(Icons.flip_camera_ios,
                          color: Colors.white),
                      onPressed: _isRecording ? null : _switchCamera,
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Bottom controls: record button
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.only(bottom: 32),
                child: Center(
                  child: _isSaving
                      ? const Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircularProgressIndicator(color: Colors.white),
                            SizedBox(height: 12),
                            Text('Saving…',
                                style: TextStyle(color: Colors.white)),
                          ],
                        )
                      : _RecordButton(
                          isRecording: _isRecording,
                          onPressed: _isInitialized ? _toggleRecording : null,
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _UploadBadge extends StatelessWidget {
  final int count;
  const _UploadBadge({required this.count});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.black54,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white24),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 12,
            height: 12,
            child: CircularProgressIndicator(
                strokeWidth: 1.5, color: Colors.white70),
          ),
          const SizedBox(width: 5),
          Text(
            '$count',
            style: const TextStyle(
                color: Colors.white70,
                fontSize: 12,
                fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class _RecordButton extends StatelessWidget {
  final bool isRecording;
  final VoidCallback? onPressed;

  const _RecordButton({required this.isRecording, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        width: 80,
        height: 80,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 4),
        ),
        child: Center(
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: isRecording ? 30 : 62,
            height: isRecording ? 30 : 62,
            decoration: BoxDecoration(
              color: Colors.red,
              borderRadius: BorderRadius.circular(isRecording ? 6 : 31),
            ),
          ),
        ),
      ),
    );
  }
}
