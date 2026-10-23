3. For EACH function/region you analyze:
   - Read and understand the code
   - Check for security vulnerabilities
   {review_step}
4. For confirmed vulnerabilities:
   - Verify it's a real issue by reading the surrounding code
   - Check if there are mitigations elsewhere
   - Use `report_pr_review` to submit the finding
5. Continue reviewing until you've thoroughly analyzed ALL changed functions

Remember:
- Focus on security issues only
{mark_reminder}- Report each vulnerability separately with `report_pr_review`
- Provide exact line numbers from the files
- Include clear explanations and suggested fixes
- CONTINUE after each finding - don't stop early!