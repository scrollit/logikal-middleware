# -*- coding: utf-8 -*-
# ARCHIVED: Elevation-related code removed from phase_sync_service.py
# This file contains the elevation functionality that was removed to focus on phase sync testing
# Will be restored later when phases are working correctly

"""
ARCHIVED ELEVATION FUNCTIONALITY

The following methods and code blocks were removed from phase_sync_service.py:

1. sync_elevations_only_for_all_projects() method
2. _sync_elevations_through_api() method  
3. All elevation-related variables and processing in _sync_project_data_through_api()
4. Elevation counting and error handling in various methods

This code will be restored once phase synchronization is working correctly.
"""

# ARCHIVED METHOD: sync_elevations_only_for_all_projects
def sync_elevations_only_for_all_projects(self):
    """
    Initiates a staged sync using the new master sync orchestration.
    """
    # Create master sync record
    master_sync = self.env['mbioe.master.sync'].create({
        'name': f"Phase Sync (Elevations Only) {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}",
        'sync_type': 'elevations',
        'state': 'draft'
    })
    
    # Start the master sync
    return master_sync.action_start_sync()

# ARCHIVED METHOD: _sync_elevations_through_api
def _sync_elevations_through_api(self, api_client, project, phase):
    """
    Sync elevations through MBIOE API (not file system).
    """
    elevations_count = 0
    errors = []

    try:
        # Select the phase through MBIOE API
        api_client.select_phase(phase.identifier)

        # Get elevations through MBIOE API (not file system)
        api_elevations = api_client.get_elevations()
        if not api_elevations:
            _logger.info(f"No elevations found for phase {phase.name} ({phase.identifier})")
            return 0, []

        # Mark existing elevations as 'to_remove'
        existing_elevations = self.env['mbioe.project.elevation'].search([('phase_id', '=', phase.id)])
        existing_elevations.write({'sync_status': 'to_remove'})

        # Process each elevation through MBIOE API
        for api_elevation_data in api_elevations:
            elevation_identifier = api_elevation_data.get('id')
            if not elevation_identifier:
                errors.append(f"Elevation data missing identifier for phase {phase.name}")
                continue

            elevation = self.env['mbioe.project.elevation'].search([
                ('phase_id', '=', phase.id),
                ('identifier', '=', elevation_identifier)
            ], limit=1)

            if elevation:
                elevation.update_from_api_data(api_elevation_data)
                _logger.debug(f"Updated elevation: {elevation.name} ({elevation.identifier})")
            else:
                elevation = self.env['mbioe.project.elevation'].create_from_api_data(
                    api_elevation_data, project.id, phase.id
                )
                _logger.debug(f"Created new elevation: {elevation.name} ({elevation.identifier})")
            
            elevations_count += 1

        # Remove elevations not found in the latest API sync
        self.env['mbioe.project.elevation'].search([
            ('phase_id', '=', phase.id),
            ('sync_status', '=', 'to_remove')
        ]).unlink()

        phase.write({'last_api_sync': fields.Datetime.now(), 'sync_status': 'unchanged'})

    except Exception as e:
        error_msg = f"Error syncing elevations through API for phase {phase.name}: {str(e)}"
        errors.append(error_msg)
        _logger.error(error_msg)

    return elevations_count, errors

# ARCHIVED CODE BLOCKS:
# The following code blocks were removed from _sync_project_data_through_api():

"""
# Sync elevations for this phase through MBIOE API
phase_elevations_count, phase_errors = self._sync_elevations_through_api(
    api_client, project, phase
)
elevations_count += phase_elevations_count
errors.extend(phase_errors)
"""

# ARCHIVED VARIABLES:
# The following variables were removed from various methods:
# - elevations_count (in _sync_project_using_working_pattern)
# - total_elevations (in sync_single_project_phases)
# - phase_elevations_count (in _sync_project_data_through_api)

# ARCHIVED LOGGING:
# The following log messages were removed:
# - "Successfully synced project {project.name}: {phases_count} phases, {elevations_count} elevations"
# - Elevation-related error messages and processing

# ARCHIVED RETURN VALUES:
# The following return values were modified to remove elevation counts:
# - _sync_project_using_working_pattern: (phases_count, 0, errors) instead of (phases_count, elevations_count, errors)
# - _sync_project_data_through_api: (phases_count, 0, errors) instead of (phases_count, elevations_count, errors)
