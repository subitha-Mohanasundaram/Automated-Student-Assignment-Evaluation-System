import java.util.*;

public class student_solution {
    public static String solve(String input) {
        String[] parts = input.trim().split("\\s+");
        int n = Integer.parseInt(parts[0]);
        int d = Integer.parseInt(parts[1]);

        int[] a = new int[n];
        for (int i = 0; i < n; i++) {
            a[i] = Integer.parseInt(parts[i + 2]);
        }

        d = d % n;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) {
            if (i > 0) sb.append(" ");
            sb.append(a[(i + d) % n]);
        }
        return sb.toString();
    }
}
