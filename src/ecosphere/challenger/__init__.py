# src/ecosphere/challenger/__init__.py
"""BeaconWise V8 Challenger Architecture.

Three-role consensus: Primary → Validator → Challenger.
The Challenger produces adversarial governance pressure, not answers.

Cost curve (V8 default):
  70-85%: 1 model call (Primary only)
  10-25%: +1 validator
  2-10%:  +challenger
"""
