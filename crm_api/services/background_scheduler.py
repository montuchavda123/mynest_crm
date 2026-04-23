import threading
import time
import logging
import os
from django.conf import settings

logger = logging.getLogger("crm_api")

def start_background_sync():
    """
    Function to be run in a background thread to periodically sync Google Sheets.
    """
    # Prevent running twice when Django reloader is active
    if os.environ.get('RUN_MAIN') != 'true':
        return

    def run_sync():
        logger.info("Background Google Sheets sync thread started.")
        
        # Initial wait to let the server start up fully
        time.sleep(5)
        
        while True:
            try:
                # Import inside the function to avoid circular imports
                from crm_api.services.google_sheets_service import GoogleSheetsService
                
                enabled = getattr(settings, "GOOGLE_SHEET_SYNC_ENABLED", False)
                sheet_id = getattr(settings, "GOOGLE_SHEET_ID", None)
                sheet_range = getattr(settings, "GOOGLE_SHEET_RANGE", "Sheet1!A:Z")
                
                if enabled and sheet_id:
                    logger.info("Executing periodic Google Sheets sync...")
                    service = GoogleSheetsService()
                    data = service.fetch_sheet_data(sheet_id, sheet_range)
                    
                    if data:
                        stats = service.process_rows(data)
                        logger.info(f"Sync complete: {stats['created']} created, {stats['duplicates']} duplicates.")
                    else:
                        logger.warning("Periodic sync: No data fetched from sheet.")
                else:
                    if not enabled:
                        logger.debug("Periodic sync: Disabled in settings.")
                    if not sheet_id:
                        logger.warning("Periodic sync: GOOGLE_SHEET_ID is missing.")

            except Exception as e:
                logger.error(f"Error in background sync thread: {str(e)}")
            
            # Sleep for 5 minutes (300 seconds)
            time.sleep(300)

    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
