# const.py

date_posted = {
    "param": "f_TPR",
    "options": {
        "Any time": None,
        "Past month": "r2592000",
        "Past week": "r604800",
        "Past day": "r86400"
    },
    "allowMultiple": False
}

experience_level = {
    "param": "f_E",
    "options": {
        "Internship": "1",
        "Entry level": "2",
        "Associate": "3",
        "Mid-Senior level": "4",
        "Director": "5",
        "Executive": "6"
    },
    "allowMultiple": True
}

job_type = {
    "param": "f_JT",
    "options": {
        "Full-time": "F",
        "Part-time": "P",
        "Contract": "C",
        "Temporary": "T",
        "Volunteer": "V",
        "Internship": "I",
        "Other": "O"
    },
    "allowMultiple": True
}

remote = {
    "param": "f_WT",
    "options": {
        "On-site": "1",
        "Remote": "2",
        "Hybrid": "3"
    },
    "allowMultiple": True
}

FILTERS = {
    "date_posted": date_posted,
    "experience_level": experience_level,
    "job_type": job_type,
    "remote": remote,
}

