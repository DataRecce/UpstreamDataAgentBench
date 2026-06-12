def validate(llm_output: str):
    """
    Validate that all CPC codes in ground truth appear in the LLM output.

    - Case-insensitive
    - No proximity constraint
    - Each code must appear at least once

    Returns:
        (True, "OK") if all CPC codes are present
        (False, reason) if any are missing
    """
    ground_truth = [
        "A22B", "A23J", "A23P", "A24D", "A24F", "A41G", "A47F", "A61G", "A61H", "A61P",
        "A62D", "A63H", "B04B", "B07B", "B08B", "B09C", "B21J", "B22F", "B24B", "B25B",
        "B25D", "B27C", "B27M", "B60D", "B60L", "B60P", "B61H", "B63C", "B63G", "B65G",
        "B66F", "C01D", "C01G", "C21B", "C21C", "C22C", "D21B", "E01H", "E02B", "E02D",
        "E03B", "E04B", "E04G", "E21D", "E21F", "F02K", "F04F", "F16M", "F25J", "F26B",
        "G01H", "G01L", "G01S", "G05D", "G06N", "G06Q", "G06T", "G06V", "G08G", "G09F",
        "G10L", "G16B", "G16C", "G16H", "G21F", "H01M", "H02B", "H02G", "H02J", "H03H",
        "H04K", "H05F"
    ]

    llm_lower = llm_output.lower()

    for code in ground_truth:
        if code.lower() not in llm_lower:
            reason = f"Missing CPC code: {code}"
            
            return False, reason

    return True, "All CPC codes present in LLM output."
