import 'package:http/http.dart' as http;
import 'auth_service.dart';

class VideoUploadService {
  final String baseUrl;

  VideoUploadService({required this.baseUrl});

  /// Uploads the video file at [filePath] to POST /videos on the API.
  /// Throws on non-201 responses.
  Future<void> uploadVideo(String filePath) async {
    final token = await AuthService.instance.getToken(baseUrl);
    final uri = Uri.parse('$baseUrl/videos');
    final request = http.MultipartRequest('POST', uri)
      ..headers['Authorization'] = 'Bearer $token'
      ..files.add(await http.MultipartFile.fromPath('file', filePath));

    final streamed = await request.send();
    if (streamed.statusCode != 201) {
      final body = await streamed.stream.bytesToString();
      throw Exception('Upload failed (${streamed.statusCode}): $body');
    }
  }
}
