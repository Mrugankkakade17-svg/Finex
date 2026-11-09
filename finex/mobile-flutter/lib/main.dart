// Finex Mobile App Entry Point
import 'package:flutter/material.dart';

void main() {
  runApp(const FinexApp());
}

class FinexApp extends StatelessWidget {
  const FinexApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Finex',
      home: const Scaffold(
        body: Center(
          child: Text('Finex'),
        ),
      ),
    );
  }
}
