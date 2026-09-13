## Description: <br>
Tencent COS helps agents manage Tencent Cloud Object Storage, CI media and document processing, MetaInsight search, and knowledge-base workflows through guided shell commands and JSON-returning scripts. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[shawnminh](https://clawhub.ai/user/shawnminh) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
Developers and operators use this skill to configure Tencent Cloud COS access, upload and manage objects, process images, media, and documents with CI, create searchable knowledge bases, and retrieve content from Tencent Cloud storage. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: The skill can give an agent broad Tencent Cloud COS and CI authority, including object deletion, bulk deletion, signed links, and raw CI API calls. <br>
Mitigation: Use a least-privilege Tencent sub-account or temporary STS credentials, avoid root or broad permanent keys, and manually confirm provider, bucket, file paths, signed-link expiry, ci-request calls, and all delete or bulk-delete actions before execution. <br>
Risk: Credential persistence can store Tencent Cloud secrets locally when users choose persistent setup. <br>
Mitigation: Prefer ephemeral environment variables or STS credentials, avoid persistence unless necessary, encrypt persisted credentials when used, and remove local credential files when access is no longer needed. <br>
Risk: Knowledge-base and indexing workflows can upload, bind, index, and search user documents in Tencent Cloud services. <br>
Mitigation: Confirm the target dataset, bucket, files, and indexing intent before uploading or binding documents, especially for sensitive or regulated content. <br>
Risk: COS and CI operations are paid Tencent Cloud services and may incur usage costs. <br>
Mitigation: Confirm that the user accepts Tencent COS and CI pricing before running storage, processing, indexing, or batch actions. <br>


## Reference(s): <br>
- [ClawHub Tencent COS Skill](https://clawhub.ai/shawnminh/skills/tencent-cos-skill) <br>
- [Tencent COS API Reference](artifact/references/api_reference.md) <br>
- [Tencent COS Node.js SDK Documentation](https://cloud.tencent.com/document/product/436/8629) <br>
- [Tencent COS Node.js SDK GitHub](https://github.com/tencentyun/cos-nodejs-sdk-v5) <br>
- [Tencent Cloud CI Documentation](https://cloud.tencent.com/document/product/460) <br>
- [Tencent COS Pricing](https://cloud.tencent.com/document/product/436/16871) <br>
- [Tencent CI Pricing](https://cloud.tencent.com/document/product/460/6970) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, shell commands, configuration, guidance, JSON] <br>
**Output Format:** [Markdown guidance with shell command examples and JSON command output] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Requires Tencent Cloud credentials, Region, and Bucket configuration; optional DatasetName, custom domain settings, and STS token can alter command behavior.] <br>

## Skill Version(s): <br>
1.1.8 (source: server release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
