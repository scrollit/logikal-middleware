import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from services.directory_sync_service import DirectorySyncService
from services.auth_service import AuthService

logger = logging.getLogger(__name__)


class ConcurrencyTestService:
    """Service for testing optimal concurrent request limits"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
    
    async def test_concurrent_limits(self, base_url: str, username: str, password: str, 
                                   max_workers: int = 10) -> Dict:
        """
        Test different concurrent worker limits to find optimal settings
        """
        test_results = []
        
        logger.info(f"Starting concurrency limit testing (1 to {max_workers} workers)")
        
        for worker_count in range(1, max_workers + 1):
            logger.info(f"Testing with {worker_count} concurrent workers")
            
            try:
                result = await self._test_with_workers(
                    base_url, username, password, worker_count
                )
                test_results.append(result)
                
                # If we hit significant errors, stop testing higher limits
                if result['error_rate'] > 0.2:  # 20% error rate threshold
                    logger.warning(f"High error rate ({result['error_rate']:.1%}) with {worker_count} workers. Stopping tests.")
                    break
                    
            except Exception as e:
                logger.error(f"Test failed with {worker_count} workers: {str(e)}")
                test_results.append({
                    'workers': worker_count,
                    'success': False,
                    'error': str(e),
                    'duration_seconds': 0,
                    'error_rate': 1.0
                })
                break
        
        # Analyze results to find optimal limit
        optimal_analysis = self._analyze_optimal_limit(test_results)
        
        return {
            'test_results': test_results,
            'optimal_analysis': optimal_analysis,
            'recommendation': self._generate_recommendation(optimal_analysis)
        }
    
    async def _test_with_workers(self, base_url: str, username: str, password: str, 
                               worker_count: int) -> Dict:
        """Test directory sync with specific number of workers"""
        start_time = time.time()
        
        try:
            # Create a subset of root directories for testing
            root_directories = await self._get_test_root_directories(base_url, username, password)
            
            # Limit test to first 5 directories to keep test time reasonable
            test_directories = root_directories[:5]
            
            logger.info(f"Testing {worker_count} workers with {len(test_directories)} test directories")
            
            # Test concurrent processing
            semaphore = asyncio.Semaphore(worker_count)
            results = await self._test_concurrent_processing(
                base_url, username, password, test_directories, semaphore
            )
            
            duration = time.time() - start_time
            
            # Calculate metrics
            successful_tasks = sum(1 for r in results if isinstance(r, int) and r > 0)
            failed_tasks = len(results) - successful_tasks
            error_rate = failed_tasks / len(results) if results else 0
            
            return {
                'workers': worker_count,
                'success': True,
                'duration_seconds': round(duration, 2),
                'test_directories': len(test_directories),
                'successful_tasks': successful_tasks,
                'failed_tasks': failed_tasks,
                'error_rate': error_rate,
                'directories_processed': sum(r for r in results if isinstance(r, int))
            }
            
        except Exception as e:
            duration = time.time() - start_time
            return {
                'workers': worker_count,
                'success': False,
                'duration_seconds': round(duration, 2),
                'error': str(e),
                'error_rate': 1.0
            }
    
    async def _test_concurrent_processing(self, base_url: str, username: str, password: str,
                                        test_directories: List[Dict], semaphore: asyncio.Semaphore) -> List:
        """Test concurrent processing with semaphore"""
        
        async def process_with_semaphore(root_directory):
            async with semaphore:
                root_name = root_directory.get('name', 'Unknown')
                
                try:
                    # Create dedicated session for this test
                    success, token = await self.auth_service.authenticate(base_url, username, password)
                    
                    if not success:
                        logger.error(f"Authentication failed for test directory: {root_name}")
                        return 0
                    
                    # Test directory selection
                    from services.directory_service import DirectoryService
                    directory_service = DirectoryService(self.db, token, base_url)
                    
                    root_path = root_directory.get('path') or root_directory.get('name', '')
                    success, message = await directory_service.select_directory(root_path)
                    
                    if success:
                        # Test getting children
                        success, children, message = await directory_service.get_directories()
                        return len(children) + 1 if success else 0  # +1 for the root directory
                    else:
                        logger.warning(f"Failed to select directory {root_name}: {message}")
                        return 0
                        
                except Exception as e:
                    logger.error(f"Error testing directory {root_name}: {str(e)}")
                    return 0
        
        # Create and execute tasks
        tasks = [process_with_semaphore(rd) for rd in test_directories]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    async def _get_test_root_directories(self, base_url: str, username: str, password: str) -> List[Dict]:
        """Get root directories for testing"""
        try:
            # Create discovery session
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Get root directories
            from services.directory_service import DirectoryService
            directory_service = DirectoryService(self.db, token, base_url)
            success, directories, message = await directory_service.get_directories()
            
            if not success:
                raise Exception(f"Failed to get root directories: {message}")
            
            return directories
            
        except Exception as e:
            logger.error(f"Failed to get test root directories: {str(e)}")
            return []
    
    def _analyze_optimal_limit(self, test_results: List[Dict]) -> Dict:
        """Analyze test results to find optimal concurrent limit"""
        
        if not test_results:
            return {'optimal_workers': 1, 'reason': 'No test results'}
        
        # Find the point where error rate starts increasing significantly
        optimal_workers = 1
        best_performance = 0
        
        for result in test_results:
            if not result.get('success', False):
                break
                
            # Consider both speed and reliability
            # Speed factor: lower duration is better
            # Reliability factor: lower error rate is better
            speed_factor = 1.0 / max(result.get('duration_seconds', 1), 1)
            reliability_factor = 1.0 - result.get('error_rate', 0)
            performance_score = speed_factor * reliability_factor
            
            if performance_score > best_performance and result.get('error_rate', 0) <= 0.1:  # Max 10% error rate
                best_performance = performance_score
                optimal_workers = result.get('workers', 1)
        
        # Find the maximum safe workers (where error rate stays low)
        max_safe_workers = 1
        for result in test_results:
            if result.get('success', False) and result.get('error_rate', 0) <= 0.05:  # Max 5% error rate
                max_safe_workers = result.get('workers', 1)
            else:
                break
        
        return {
            'optimal_workers': optimal_workers,
            'max_safe_workers': max_safe_workers,
            'best_performance_score': best_performance,
            'test_count': len(test_results)
        }
    
    def _generate_recommendation(self, analysis: Dict) -> Dict:
        """Generate recommendation based on analysis"""
        
        optimal = analysis.get('optimal_workers', 1)
        max_safe = analysis.get('max_safe_workers', 1)
        
        if max_safe >= 5:
            recommendation = "aggressive"
            suggested_workers = max_safe
        elif max_safe >= 3:
            recommendation = "moderate" 
            suggested_workers = optimal
        else:
            recommendation = "conservative"
            suggested_workers = min(optimal, 2)
        
        return {
            'recommendation': recommendation,
            'suggested_workers': suggested_workers,
            'reasoning': f"Based on testing, {recommendation} approach recommended",
            'optimal_workers': optimal,
            'max_safe_workers': max_safe
        }
