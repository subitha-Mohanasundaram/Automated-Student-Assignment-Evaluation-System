public class student_solution {
    public static String solve(String input) {
        String[] parts = input.split("\\|");
        String[] arr = parts[0].trim().split("\\s+");
        int k = Integer.parseInt(parts[1]) %% arr.length;
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < arr.length; i++) {
            if (i > 0) out.append(" ");
            out.append(arr[(i + k) %% arr.length]);
        }
        return out.toString();
    }
}
