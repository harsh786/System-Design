import java.util.*;

/**
 * Problem 22: Exclusive Time of Functions (LeetCode 636)
 * 
 * Single-threaded CPU runs n functions. Given logs, compute exclusive time of each.
 * 
 * Approach: Stack tracks currently running function. On start, push function.
 * On end, pop and calculate time. Subtract child time from parent.
 * 
 * Time Complexity: O(n) where n = number of logs
 * Space Complexity: O(n/2) max stack depth
 * 
 * Production Analogy: Like distributed tracing (Jaeger/Zipkin) computing exclusive
 * time per span by subtracting child span durations from parent.
 */
public class Problem22_ExclusiveTimeOfFunctions {

    public static int[] exclusiveTime(int n, List<String> logs) {
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        int prevTime = 0;
        for (String log : logs) {
            String[] parts = log.split(":");
            int id = Integer.parseInt(parts[0]);
            String type = parts[1];
            int time = Integer.parseInt(parts[2]);
            if (type.equals("start")) {
                if (!stack.isEmpty()) {
                    result[stack.peek()] += time - prevTime;
                }
                stack.push(id);
                prevTime = time;
            } else {
                result[stack.pop()] += time - prevTime + 1;
                prevTime = time + 1;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(exclusiveTime(2, 
            Arrays.asList("0:start:0","1:start:2","1:end:5","0:end:6")))); // [3,4]
        System.out.println(Arrays.toString(exclusiveTime(1, 
            Arrays.asList("0:start:0","0:start:2","0:end:5","0:start:6","0:end:6","0:end:7")))); // [8]
    }
}
