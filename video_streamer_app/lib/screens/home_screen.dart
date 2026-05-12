import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';
import '../services/video_storage_service.dart';
import 'camera_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  List<VideoFile> _videos = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadVideos();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // Refresh when app comes back to foreground.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _loadVideos();
  }

  Future<void> _loadVideos() async {
    final settings = context.read<SettingsProvider>();
    final videos =
        await VideoStorageService.listVideos(settings.syncFolderPath);
    if (mounted) setState(() { _videos = videos; _loading = false; });
  }

  Future<void> _openCamera() async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No cameras available')),
        );
      }
      return;
    }

    if (!mounted) return;
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CameraScreen(cameras: cameras),
      ),
    );
    _loadVideos();
  }

  Future<void> _confirmDelete(VideoFile video) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete video?'),
        content: Text(video.name),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await VideoStorageService.deleteVideo(video.path);
      _loadVideos();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: const Text(
          'Video Ingestion',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            onPressed: () async {
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SettingsScreen()),
              );
              _loadVideos();
            },
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _videos.isEmpty
              ? _buildEmptyState()
              : _buildVideoList(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCamera,
        icon: const Icon(Icons.videocam),
        label: const Text('Record'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
      ),
    );
  }

  Widget _buildEmptyState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.videocam_off, size: 72, color: Colors.white24),
          SizedBox(height: 16),
          Text(
            'No recordings yet',
            style: TextStyle(color: Colors.white54, fontSize: 18),
          ),
          SizedBox(height: 8),
          Text(
            'Tap Record to start',
            style: TextStyle(color: Colors.white30, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoList() {
    return RefreshIndicator(
      onRefresh: _loadVideos,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _videos.length,
        separatorBuilder: (_, __) =>
            const Divider(color: Colors.white12, height: 1),
        itemBuilder: (_, index) {
          final video = _videos[index];
          return ListTile(
            leading: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: Colors.white10,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.play_circle_outline,
                  color: Colors.white54, size: 28),
            ),
            title: Text(
              video.name,
              style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.w500),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              '${video.formattedDate}  •  ${video.formattedSize}',
              style: const TextStyle(color: Colors.white38, fontSize: 12),
            ),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.white38),
              onPressed: () => _confirmDelete(video),
            ),
          );
        },
      ),
    );
  }
}
