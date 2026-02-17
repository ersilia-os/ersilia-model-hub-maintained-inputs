# Maintained inputs for the Ersilia Model Hub
This repository contains maintained input data to be used in the Ersilia Model Hub precalculations

* Please visit the [Ersilia Book](https://ersilia.gitbook.io/ersilia-book) to learn more about the input types.
* Data from this repository is mainly accessed by the `example` command of the [Ersilia CLI](https://github.com/ersilia-os/ersilia).

**Note**: The repository is organized following the input type logic of Ersilia. For now, we only have compound inputs. Users are encouraged to use these inputs when testing compounds.

## 📦 Data & Artifact Management
This repository uses [EOSVC](https://github.com/ersilia-os/eosvc/tree/main) (Ersilia Object Storage Version Control)  to manage large files that are too big for Git. While the source code lives here on GitHub, the datasets and model outputs are stored in S3. EOSVC does not handle Git operations. Use standard git commands (pull, push, commit) for code changes, and use eosvc specifically for syncing the following directories:
- data/
- output/

### Prerequisites
Ensure you have the EOSVC CLI installed and configured with the necessary S3 credentials.

## About the Ersilia Model Hub
This repository is tightly related to the [Ersilia Model Hub](https://ersilia.io/model-hub). This tool is maintained by the [Ersilia Open Source Initiative](https://ersilia.io), an open-source nonprofit organisation aimed at developing AI/ML tools to support research in the Global South.
