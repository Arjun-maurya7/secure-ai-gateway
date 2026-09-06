from detection.engine import DetectionEngine

text = "Rahul Maurya sent me the document. my phone no is 7054267380 and email is arjunmaru3893@gmail.com"

engine = DetectionEngine()
entities = engine.detect(text)

for entity in entities:
    print(entity)