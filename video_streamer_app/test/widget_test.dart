import 'package:flutter_test/flutter_test.dart';
import 'package:video_ingestion/main.dart';

void main() {
  testWidgets('App renders without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(const VideoIngestionApp());
    expect(find.text('Video Ingestion'), findsOneWidget);
  });
}
