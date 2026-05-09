import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kSubfolderKey = 'sync_subfolder';
const _kDefaultSubfolder = 'MobiusVideos';
const _kApiUrlKey = 'api_url';

class SettingsProvider extends ChangeNotifier {
  String _subfolder = _kDefaultSubfolder;
  String _documentsPath = '';
  String _apiUrl = '';

  String get subfolder => _subfolder;
  String get documentsPath => _documentsPath;
  String get apiUrl => _apiUrl;

  /// The full path where videos are saved. This is what you point Mobius Sync at.
  String get syncFolderPath => p.join(_documentsPath, _subfolder);

  Future<void> load() async {
    final docs = await getApplicationDocumentsDirectory();
    _documentsPath = docs.path;

    final prefs = await SharedPreferences.getInstance();
    _subfolder = prefs.getString(_kSubfolderKey) ?? _kDefaultSubfolder;
    _apiUrl = prefs.getString(_kApiUrlKey) ?? '';

    await _ensureSyncFolderExists();
    notifyListeners();
  }

  Future<void> setSubfolder(String name) async {
    final sanitized = name.trim().replaceAll(RegExp(r'[^\w\-. ]'), '_');
    if (sanitized.isEmpty) return;

    _subfolder = sanitized;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kSubfolderKey, _subfolder);
    await _ensureSyncFolderExists();
    notifyListeners();
  }

  Future<void> setApiUrl(String url) async {
    _apiUrl = url.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kApiUrlKey, _apiUrl);
    notifyListeners();
  }

  Future<void> _ensureSyncFolderExists() async {
    final dir = Directory(syncFolderPath);
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
  }
}
