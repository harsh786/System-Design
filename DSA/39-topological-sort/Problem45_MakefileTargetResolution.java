import java.util.*;

/**
 * Problem: Makefile Target Resolution
 * Resolve make targets with dependencies, detect cycles.
 *
 * Approach: DFS topological sort from target, collecting all needed builds
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: GNU Make / Bazel target resolution.
 */
public class Problem45_MakefileTargetResolution {

    public List<String> resolveBuild(String target, Map<String, List<String>> makefile) {
        List<String> order = new ArrayList<>();
        Set<String> visited = new HashSet<>(), inProgress = new HashSet<>();
        if (!dfs(target, makefile, visited, inProgress, order)) return Collections.emptyList();
        return order;
    }

    private boolean dfs(String t, Map<String, List<String>> makefile, Set<String> visited, Set<String> inProgress, List<String> order) {
        if (inProgress.contains(t)) return false; // cycle
        if (visited.contains(t)) return true;
        inProgress.add(t);
        for (String dep : makefile.getOrDefault(t, Collections.emptyList()))
            if (!dfs(dep, makefile, visited, inProgress, order)) return false;
        inProgress.remove(t);
        visited.add(t);
        order.add(t);
        return true;
    }

    public static void main(String[] args) {
        Problem45_MakefileTargetResolution solver = new Problem45_MakefileTargetResolution();
        Map<String, List<String>> mf = new HashMap<>();
        mf.put("all", Arrays.asList("main.o", "utils.o"));
        mf.put("main.o", Arrays.asList("main.c", "utils.h"));
        mf.put("utils.o", Arrays.asList("utils.c", "utils.h"));
        System.out.println(solver.resolveBuild("all", mf));
    }
}
