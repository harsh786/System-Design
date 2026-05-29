/**
 * Problem: Fizz Buzz (LeetCode 412)
 * Approach: Simple modulo simulation
 * Complexity: O(n) time, O(1) space per element
 * Production Analogy: Rule-based data transformation pipelines
 */
import java.util.*;
public class Problem49_FizzBuzz {
    public List<String> fizzBuzz(int n) {
        List<String> res = new ArrayList<>();
        for (int i = 1; i <= n; i++) {
            if (i%15==0) res.add("FizzBuzz");
            else if (i%3==0) res.add("Fizz");
            else if (i%5==0) res.add("Buzz");
            else res.add(String.valueOf(i));
        }
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem49_FizzBuzz().fizzBuzz(15));
    }
}
