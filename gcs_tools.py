import subprocess
import logging
from typing import List

logger = logging.getLogger(__name__)

def move_files_to_bucket(filenames: List[str], bucket_name: str = "my-archive-bucket") -> str:
    """Moves local files to a GCS bucket using gsutil. 
    
    This function wraps the 'gsutil mv' command, which ensures that the 
    remote object is successfully created and verified before the local 
    file is deleted.

    Args:
        filenames: List of local file paths to move.
        bucket_name: The destination GCS bucket.

    Returns:
        A summary string of the operation results.
    """
    results = []
    for file in filenames:
        try:
            # Construct the gsutil command
            # gsutil mv performs a copy, verifies the hash, and then deletes the source.
            cmd = ["gsutil", "mv", file, f"gs://{bucket_name}/"]
            
            logger.info(f"Executing: {' '.join(cmd)}")
            
            # Execute command
            # In a real environment, this would move the file.
            subprocess.run(
                cmd, 
                check=True, 
                capture_output=True, 
                text=True
            )
            results.append(f"Successfully moved {file} to gs://{bucket_name}/")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to move {file}. Error: {e.stderr.strip()}"
            logger.error(error_msg)
            results.append(error_msg)
        except FileNotFoundError:
             results.append(f"Error: gsutil command not found. Is Cloud SDK installed?")

    return "\n".join(results)
