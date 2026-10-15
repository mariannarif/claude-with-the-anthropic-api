import unittest
from main_test import fibonacci

class TestFibonacci(unittest.TestCase):
    def test_empty_sequence(self):
        """Test when n is 0 or negative"""
        self.assertEqual(fibonacci(0), [])
        self.assertEqual(fibonacci(-1), [])
        
    def test_single_element(self):
        """Test when n is 1"""
        self.assertEqual(fibonacci(1), [0])
        
    def test_two_elements(self):
        """Test when n is 2"""
        self.assertEqual(fibonacci(2), [0, 1])
        
    def test_multiple_elements(self):
        """Test with more elements in the sequence"""
        self.assertEqual(fibonacci(5), [0, 1, 1, 2, 3])
        self.assertEqual(fibonacci(8), [0, 1, 1, 2, 3, 5, 8, 13])
        
    def test_large_sequence(self):
        """Test with a larger number of elements"""
        result = fibonacci(10)
        self.assertEqual(len(result), 10)
        self.assertEqual(result, [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

if __name__ == "__main__":
    unittest.main()