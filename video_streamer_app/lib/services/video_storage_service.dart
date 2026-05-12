import 'dart:io';
import 'package:camera/camera.dart';
import 'package:intl/intl.dart';
import 'package:path/path.dart' as p;

class VideoFile {
  final String path;
  final DateTime createdAt;
  final int sizeBytes;

  VideoFile({
    required this.path,
    required this.createdAt,
    required this.sizeBytes,
  });

  String get name => p.basename(path);

  String get formattedSize {
    if (sizeBytes < 1024 * 1024) {
      return '${(sizeBytes / 1024).toStringAsFixed(1)} KB';
    }
    return '${(sizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String get formattedDate =>
      DateFormat('MMM d, yyyy  HH:mm').format(createdAt);
}

class VideoStorageService {
  /// Moves the recorded XFile into [syncFolderPath] with a timestamped name.
  /// Returns the final [VideoFile] on success.
  static Future<VideoFile> saveRecording(
    XFile recording,
    String syncFolderPath,
  ) async {
    final timestamp = DateFormat('yyyyMMdd_HHmmss').format(DateTime.now());
    final destination = p.join(syncFolderPath, 'VID_$timestamp.mp4');

    final src = File(recording.path);
    final dest = await src.copy(destination);

    // Clean up the temp file left by the camera plugin.
    await src.delete();

    final stat = await dest.stat();
    return VideoFile(
      path: dest.path,
      createdAt: stat.modified,
      sizeBytes: stat.size,
    );
  }

  /// Lists all video files in [syncFolderPath], newest first.
  static Future<List<VideoFile>> listVideos(String syncFolderPath) async {
    final dir = Directory(syncFolderPath);
    if (!await dir.exists()) return [];

    final entries = await dir
        .list()
        .where((e) => e is File && e.path.toLowerCase().endsWith('.mp4'))
        .cast<File>()
        .toList();

    final files = await Future.wait(entries.map((f) async {
      final stat = await f.stat();
      return VideoFile(
        path: f.path,
        createdAt: stat.modified,
        sizeBytes: stat.size,
      );
    }));

    files.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return files;
  }

  static Future<void> deleteVideo(String path) async {
    final file = File(path);
    if (await file.exists()) await file.delete();
  }
}
