import json
import os
import glob
from collections import defaultdict
from datetime import datetime
import re
import dateutil

def parse_date(date_str):
    """
    Parse date string to MM/DD/YYYY format
    Handles various formats including '08-august-2025'
    Returns original string for invalid dates (will be caught as 'N/A' later)
    """
    if not date_str or date_str == "N/A":
        return "N/A"
    date_str = str(date_str).strip()
    
    month_names = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    try:
        # Pattern 1: MM/DD/YYYY or MM-DD-YYYY
        match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', date_str)
        if match:
            month, day, year = int(match[1]), int(match[2]), int(match[3])
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 9999:
                return f"{month:02d}/{day:02d}/{year}"
        
        # Pattern 2: DD/MM/YYYY or DD-MM-YYYY
        match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', date_str)
        if match:
            day, month, year = int(match[1]), int(match[2]), int(match[3])
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 9999:
                return f"{month:02d}/{day:02d}/{year}"
        
        # Pattern 3: DD-Month-YYYY (08-august-2025)
        match = re.match(r'^(\d{1,2})[-](\w+)[-](\d{4})$', date_str, re.IGNORECASE)
        if match:
            day, month_str, year = match[1], match[2].lower(), int(match[3])
            if month_str in month_names:
                month = month_names[month_str]
                day = int(day)
                if 1 <= day <= 31:
                    return f"{month:02d}/{day:02d}/{year}"
        
        # Pattern 4: Month DD, YYYY (August 08, 2025)
        match = re.match(r'^(\w+)\s+(\d{1,2}),?\s+(\d{4})$', date_str, re.IGNORECASE)
        if match:
            month_str, day, year = match[1].lower(), int(match[2]), int(match[3])
            if month_str in month_names:
                month = month_names[month_str]
                if 1 <= day <= 31:
                    return f"{month:02d}/{day:02d}/{year}"
        
        # Pattern 5: YYYY-MM-DD (ISO format)
        match = re.match(r'^(\d{4})[-](\d{1,2})[-](\d{1,2})$', date_str)
        if match:
            year, month, day = int(match[1]), int(match[2]), int(match[3])
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{month:02d}/{day:02d}/{year}"
        
        # Try using dateutil if available (more flexible parsing)
        try:
            from dateutil.parser import parse
            date_obj = parse(date_str, fuzzy=False)
            return date_obj.strftime("%m/%d/%Y")
        except:
            pass
            
    except (ValueError, TypeError, IndexError) as e:
        print(f"Date parsing error for '{date_str}': {e}")
    return date_str

def extract_document_data(json_data, filename):
    try:
        doc_type = identify_document_type(json_data)
        
        base_data = {
            "document_type": doc_type,
            "filename": get_field_value(json_data.get('Meta', {}).get('FileName', filename)) + ".json",
            "docId": "",
        }
        
        if doc_type == "paystub":
            required_fields = ["employee_name", "employer_name", "pay_period_end_date", "pay_period_start_date", "year_to_date_earnings"]
            base_data.update({
                "employee_name": "N/A",
                "employer_name": "N/A",
                "pay_period_end_date": "N/A",
                "pay_period_start_date": "N/A", 
                "year_to_date_earnings": "N/A",
            })
            skill_name = "IC - Paystubs"
            label_map = {
                "Employee Name": "employee_name",
                "Employer Name": "employer_name", 
                "Pay Period End Date": "pay_period_end_date",
                "Pay Period Start Date": "pay_period_start_date",
                "Year to Date Earnings": "year_to_date_earnings"
            }
            
        elif doc_type == "w2":
            required_fields = ["employee_name", "employer_name", "year"]
            base_data.update({
                "employee_name": "N/A",
                "employer_name": "N/A",
                "year": "N/A",
            })
            skill_name = "IC - W2"
            label_map = {
                "Employee Name": "employee_name",
                "Employer Name": "employer_name", 
                "Year": "year"
            }
            
        else: 
            required_fields = ["name", "year", "beginning_tax_year", "ending_tax_year"]
            base_data.update({
                "name": "N/A",
                "year": "N/A",
                "beginning_tax_year": "N/A",
                "ending_tax_year": "N/A",
            })
            skill_name = "2023 1120 Corporation1"
            label_map = {
                "Name": "name",
                "1120 Year": "year",
                "Beginning Date Of Tax Year": "beginning_tax_year",
                "Ending Date Of Tax Year": "ending_tax_year"
            }
        
        skill_found = False
        for skill in json_data.get("Summary", []):
            if skill.get("SkillName") == skill_name:
                skill_found = True
                extract_from_labels(skill.get("Labels", []), label_map, base_data)
                break

        if not skill_found:
            return None, doc_type, f"Required skill '{skill_name}' not found"
        base_data = parse_date_fields(base_data, doc_type)
            
        missing_fields = []
        for field in required_fields:
            if base_data.get(field) == "N/A" or base_data.get(field) == "":
                missing_fields.append(field)
        
        if missing_fields:
            return None, doc_type, f"Missing fields: {', '.join(missing_fields)}"
        
        base_data["status"] = "original"
        
        return base_data, doc_type, None
    except Exception as e:
        return None, None, f"Error extracting data: {e}"

def parse_date_fields(base_data, doc_type):
    """Parse all date fields in the document data"""
    try:
        date_fields = []
        
        if doc_type == "paystub":
            date_fields = ["pay_period_end_date", "pay_period_start_date"]
        elif doc_type == "1120":
            date_fields = ["beginning_tax_year", "ending_tax_year"]
        # W2 typically doesn't have full date fields, mostly year only
        
        for field in date_fields:
            if field in base_data and base_data[field] != "N/A":
                parsed_date = parse_date(base_data[field])
                base_data[field] = parsed_date
        
        return base_data
    except Exception as e:
        print(f"Error in parse_date_fields: {e}")
        return base_data

def extract_from_labels(labels, label_map, base_data):
    """Recursively extract data from labels and child labels"""
    for label in labels:
        label_name = label.get("LabelName")
        
        if label_name in label_map and label.get("Values"):
            valid_values = []
            for value_item in label["Values"]:
                value = get_field_value(value_item.get("Value", "N/A"))
                if value and value != "N/A":
                    valid_values.append(value)
            if valid_values:
                base_data[label_map[label_name]] = valid_values[0]
        
        if "ChildLabels" in label and label["ChildLabels"]:
            extract_from_labels(label["ChildLabels"], label_map, base_data)

def identify_document_type(json_data):
    """Identify document type (1120, w2, or paystub)"""
    try:
        meta_type = json_data.get("Meta", {}).get("Type", "").lower()
        title = json_data.get("Title", "").lower()
        
        if any(w2_indicator in meta_type or w2_indicator in title 
               for w2_indicator in ["w2", "w-2", "income w-2"]):
            return "w2"
            
        if any(form1120_indicator in meta_type or form1120_indicator in title 
               for form1120_indicator in ["1120", "form 1120"]):
            return "1120"
            
        for skill in json_data.get("Summary", []):
            skill_name = skill.get("SkillName", "").lower()
            if "1120" in skill_name:
                return "1120"
            elif "w2" in skill_name or "w-2" in skill_name:
                return "w2"
            elif "paystub" in skill_name:
                return "paystub"

        for skill in json_data.get("Summary", []):
            skill_name = skill.get("SkillName", "")
            if skill_name == "IC - 1120":
                return "1120"
            elif skill_name == "IC - W2":
                return "w2"
            elif skill_name == "IC - Paystubs":
                return "paystub"
                
        return "paystub" 
    except Exception:
        return "paystub"

def get_field_value(value):
    """Clean and validate field value"""
    if not value or str(value).strip() in ["", " ", "N/A", "null", "None"]:
        return "N/A"
    return str(value).strip()

def get_grouping_key(doc, doc_type):
    """Get grouping key for duplicate detection"""
    try:
        if doc_type == "paystub":
            return (
                get_field_value(doc["employee_name"]),
                get_field_value(doc["employer_name"]),
                get_field_value(doc["pay_period_start_date"]),
                get_field_value(doc["pay_period_end_date"]),
                get_field_value(doc["year_to_date_earnings"])
            )
        elif doc_type == "w2":
            return (
                get_field_value(doc["employee_name"]),
                get_field_value(doc["employer_name"]),
                get_field_value(doc["year"])
            )
        else: 
            return (
                get_field_value(doc["name"]),
                get_field_value(doc["year"]),
                get_field_value(doc["beginning_tax_year"]),
                get_field_value(doc["ending_tax_year"])
            )
    except Exception:
        if doc_type == "paystub":
            return ("N/A", "N/A", "N/A", "N/A", "N/A")
        elif doc_type == "w2":
            return ("N/A", "N/A", "N/A")
        else:  
            return ("N/A", "N/A", "N/A", "N/A")

def process_documents(input_folder, output_folder):
    """Process all document files and create consolidated output"""
    os.makedirs(output_folder, exist_ok=True)
    
    documents = {"paystub": [], "w2": [], "1120": []}
    processed_files = 0
    error_files = 0
    error_file_list = []  
    
    for file_path in glob.glob(os.path.join(input_folder, "**", "*.json"), recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            data, doc_type, error_message = extract_document_data(json_data, os.path.basename(file_path))
            if data and doc_type:
                documents[doc_type].append(data)
                processed_files += 1
            else:
                error_files += 1
                error_file_list.append(os.path.basename(file_path))
                print(f"Error in {file_path}: {error_message}")
                
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {file_path}: {e}")
            error_files += 1
            error_file_list.append(os.path.basename(file_path))
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            error_files += 1
            error_file_list.append(os.path.basename(file_path))
    
    final_output = {}
    
    for doc_type, docs in documents.items():
        groups = defaultdict(list)
        for doc in docs:
            groups[get_grouping_key(doc, doc_type)].append(doc)
        
        processed_docs = []
        for group_docs in groups.values():
            group_docs.sort(key=lambda x: x["filename"])
            for i, doc in enumerate(group_docs):
                doc_copy = {k: v for k, v in doc.items() if k != "status"}
                doc_copy["status"] = "original" if i == 0 else "duplicate"
                processed_docs.append(doc_copy)
        
        if doc_type == "paystub":
            final_output["Paystubs"] = processed_docs
        elif doc_type == "w2":
            final_output["W2"] = processed_docs
        else:  
            final_output["1120"] = processed_docs
    
    output = {"finalisation": final_output}
    output_file = os.path.join(output_folder, "finalized_output.json")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing output file: {e}")
        return
    
    print(f"\nProcessing complete. Output saved to: {output_file}")
    print(f"Successfully processed: {processed_files} files")
    print(f"Files with errors: {error_files} files")
    
    if error_files > 0:
        print(f"\nFiles with errors:")
        for error_file in error_file_list:
            print(f"  - {error_file}")
    
    for doc_type, docs in documents.items():
        if doc_type == "paystub":
            count = len(final_output.get("Paystubs", []))
        elif doc_type == "w2":
            count = len(final_output.get("W2", []))
        else: 
            count = len(final_output.get("1120", []))
        print(f"Found {count} {doc_type} documents")

if __name__ == "__main__":
    process_documents("input", "output")