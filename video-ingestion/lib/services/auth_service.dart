import 'dart:convert';
import 'package:http/http.dart' as http;

const _kEmail = 'martingokcu@gmail.com';
const _kPassword = 'Abcd1234';

class AuthService {
  AuthService._();
  static final AuthService instance = AuthService._();

  String? _token;
  DateTime? _expiresAt;

  /// Returns a valid Bearer token, fetching a fresh one when the cached one
  /// is absent or within 30 seconds of expiry.
  Future<String> getToken(String baseUrl) async {
    final now = DateTime.now();
    if (_token != null && _expiresAt != null && now.isBefore(_expiresAt!)) {
      return _token!;
    }

    final credentials = base64.encode(utf8.encode('$_kEmail:$_kPassword'));
    final uri = Uri.parse('$baseUrl/auth/get_token');
    final response = await http.get(
      uri,
      headers: {'Authorization': 'Basic $credentials'},
    );

    if (response.statusCode != 200) {
      throw Exception('Auth failed (${response.statusCode}): ${response.body}');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final token = body['access_token'] as String;
    final duration = (body['access_duration'] as num).toInt();

    _token = token;
    _expiresAt = now.add(Duration(seconds: duration - 30));
    return _token!;
  }

  void clearToken() {
    _token = null;
    _expiresAt = null;
  }
}
