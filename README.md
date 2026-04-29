# 🚀 Mumzworld PDP Quality Auditor

An AI-powered system that audits marketplace product detail pages (PDPs) for quality, accuracy, and proper localization.

---

## 🔍 What it does

Given a product listing (title, description, image, and attributes in English and/or Arabic), the system generates a structured audit that includes:

- A **quality score (0–100)** with a clear rationale  
- Detection of key issues such as:
  - Missing or weak Arabic content  
  - Unsupported or misleading claims  
  - Missing attributes or safety information  
  - Title–image mismatches  
  - Generic or low-quality content  
- **Actionable fixes**, including:
  - Improved native Arabic copy (not literal translation)  
  - Suggested attribute values  
  - Rewritten titles and descriptions  
- A **refusal mode** for incomplete or insufficient inputs  

All outputs are returned as **validated structured JSON**, ensuring reliability and consistency.

---

## 🎯 Why this matters

Mumzworld operates at scale with ~250K SKUs, where ~70% of GMV comes from third-party sellers.  

At this scale:
- Manual quality control is not feasible  
- Poor PDP quality leads to:
  - Incorrect purchases  
  - Weak Arabic localization  
  - Missing safety information  
  - Reduced customer trust  

This system acts as an **automated quality gate**, helping improve catalog quality while reducing operational cost.

---
